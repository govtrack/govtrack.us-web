# Copyright (C) 2009, 2010, 2011, 2012 David Sauve
# Copyright (C) 2009, 2010 Trapeze

__author__ = 'David Sauve'
__version__ = (2, 0, 0, 'beta')

import time
import datetime
import cPickle as pickle
import os
import re
import shutil
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.encoding import force_unicode

from haystack import connections
from haystack.backends import BaseEngine, BaseSearchBackend, BaseSearchQuery, SearchNode, log_query
from haystack.constants import ID
from haystack.exceptions import HaystackError, MissingDependency
from haystack.models import SearchResult
from haystack.utils import get_identifier

try:
    import xapian
except ImportError:
    raise MissingDependency("The 'xapian' backend requires the installation of 'xapian'. Please refer to the documentation.")


DOCUMENT_ID_TERM_PREFIX = 'Q'
DOCUMENT_CUSTOM_TERM_PREFIX = 'X'
DOCUMENT_CT_TERM_PREFIX = DOCUMENT_CUSTOM_TERM_PREFIX + 'CONTENTTYPE'

MEMORY_DB_NAME = ':memory:'

DEFAULT_XAPIAN_FLAGS = (
    xapian.QueryParser.FLAG_PHRASE |
    xapian.QueryParser.FLAG_BOOLEAN |
    xapian.QueryParser.FLAG_LOVEHATE |
    xapian.QueryParser.FLAG_WILDCARD |
    xapian.QueryParser.FLAG_PURE_NOT
)


class InvalidIndexError(HaystackError):
    """Raised when an index can not be opened."""
    pass


class XHValueRangeProcessor(xapian.ValueRangeProcessor):
    def __init__(self, backend):
        # FIXME: This needs to get smarter about pulling the right backend.
        self.backend = backend or XapianSearchBackend()
        xapian.ValueRangeProcessor.__init__(self)

    def __call__(self, begin, end):
        """
        Construct a tuple for value range processing.
        `begin` -- a string in the format '<field_name>:[low_range]'
        If 'low_range' is omitted, assume the smallest possible value.
        `end` -- a string in the the format '[high_range|*]'. If '*', assume
        the highest possible value.
        Return a tuple of three strings: (column, low, high)
        """
        colon = begin.find(':')
        field_name = begin[:colon]
        begin = begin[colon + 1:len(begin)]
        for field_dict in self.backend.schema:
            if field_dict['field_name'] == field_name:
                if not begin:
                    if field_dict['type'] == 'text':
                        begin = u'a'  # TODO: A better way of getting a min text value?
                    elif field_dict['type'] == 'long':
                        begin = -sys.maxint - 1
                    elif field_dict['type'] == 'float':
                        begin = float('-inf')
                    elif field_dict['type'] == 'date' or field_dict['type'] == 'datetime':
                        begin = u'00010101000000'
                elif end == '*':
                    if field_dict['type'] == 'text':
                        end = u'z' * 100  # TODO: A better way of getting a max text value?
                    elif field_dict['type'] == 'long':
                        end = sys.maxint
                    elif field_dict['type'] == 'float':
                        end = float('inf')
                    elif field_dict['type'] == 'date' or field_dict['type'] == 'datetime':
                        end = u'99990101000000'
                if field_dict['type'] == 'float':
                    begin = _marshal_value(float(begin))
                    end = _marshal_value(float(end))
                elif field_dict['type'] == 'long':
                    begin = _marshal_value(long(begin))
                    end = _marshal_value(long(end))
                return field_dict['column'], str(begin), str(end)


class XHExpandDecider(xapian.ExpandDecider):
    def __call__(self, term):
        """
        Return True if the term should be used for expanding the search
        query, False otherwise.

        Currently, we only want to ignore terms beginning with `DOCUMENT_CT_TERM_PREFIX`
        """
        if term.startswith(DOCUMENT_CT_TERM_PREFIX):
            return False
        return True


class XapianSearchBackend(BaseSearchBackend):
    """
    `SearchBackend` defines the Xapian search backend for use with the Haystack
    API for Django search.

    It uses the Xapian Python bindings to interface with Xapian, and as
    such is subject to this bug: <http://trac.xapian.org/ticket/364> when
    Django is running with mod_python or mod_wsgi under Apache.

    Until this issue has been fixed by Xapian, it is neccessary to set
    `WSGIApplicationGroup to %{GLOBAL}` when using mod_wsgi, or
    `PythonInterpreter main_interpreter` when using mod_python.

    In order to use this backend, `PATH` must be included in the
    `connection_options`.  This should point to a location where you would your
    indexes to reside.
    """
    inmemory_db = None

    def __init__(self, connection_alias, **connection_options):
        """
        Instantiates an instance of `SearchBackend`.

        Optional arguments:
            `connection_alias` -- The name of the connection
            `language` -- The stemming language (default = 'english')
            `**connection_options` -- The various options needed to setup
              the backend.

        Also sets the stemming language to be used to `language`.
        """
        super(XapianSearchBackend, self).__init__(connection_alias, **connection_options)

        if not 'PATH' in connection_options:
            raise ImproperlyConfigured("You must specify a 'PATH' in your settings for connection '%s'." % connection_alias)

        self.path = connection_options.get('PATH')

        if self.path != MEMORY_DB_NAME and not os.path.exists(self.path):
            os.makedirs(self.path)

        self.flags = connection_options.get('FLAGS', DEFAULT_XAPIAN_FLAGS)
        self.language = getattr(settings, 'HAYSTACK_XAPIAN_LANGUAGE', 'english')
        self._schema = None
        self._content_field_name = None

    @property
    def schema(self):
        if not self._schema:
            self._content_field_name, self._schema = self.build_schema(connections[self.connection_alias].get_unified_index().all_searchfields())
        return self._schema

    @property
    def content_field_name(self):
        if not self._content_field_name:
            self._content_field_name, self._schema = self.build_schema(connections[self.connection_alias].get_unified_index().all_searchfields())
        return self._content_field_name

    def update(self, index, iterable):
        """
        Updates the `index` with any objects in `iterable` by adding/updating
        the database as needed.

        Required arguments:
            `index` -- The `SearchIndex` to process
            `iterable` -- An iterable of model instances to index

        For each object in `iterable`, a document is created containing all
        of the terms extracted from `index.full_prepare(obj)` with field prefixes,
        and 'as-is' as needed.  Also, if the field type is 'text' it will be
        stemmed and stored with the 'Z' prefix as well.

        eg. `content:Testing` ==> `testing, Ztest, ZXCONTENTtest, XCONTENTtest`

        Each document also contains an extra term in the format:

        `XCONTENTTYPE<app_name>.<model_name>`

        As well as a unique identifier in the the format:

        `Q<app_name>.<model_name>.<pk>`

        eg.: foo.bar (pk=1) ==> `Qfoo.bar.1`, `XCONTENTTYPEfoo.bar`

        This is useful for querying for a specific document corresponding to
        a model instance.

        The document also contains a pickled version of the object itself and
        the document ID in the document data field.

        Finally, we also store field values to be used for sorting data.  We
        store these in the document value slots (position zero is reserver
        for the document ID).  All values are stored as unicode strings with
        conversion of float, int, double, values being done by Xapian itself
        through the use of the :method:xapian.sortable_serialise method.
        """
        database = self._database(writable=True)
        try:
            for obj in iterable:
                document = xapian.Document()

                term_generator = xapian.TermGenerator()
                term_generator.set_database(database)
                term_generator.set_stemmer(xapian.Stem(self.language))
                if self.include_spelling is True:
                    term_generator.set_flags(xapian.TermGenerator.FLAG_SPELLING)
                term_generator.set_document(document)

                document_id = DOCUMENT_ID_TERM_PREFIX + get_identifier(obj)
                data = index.full_prepare(obj)
                weights = index.get_field_weights()
                for field in self.schema:
                    if field['field_name'] in data.keys():
                        prefix = DOCUMENT_CUSTOM_TERM_PREFIX + field['field_name'].upper()
                        value = data[field['field_name']]
                        try:
                            weight = int(weights[field['field_name']])
                        except KeyError:
                            weight = 1
                        if field['type'] == 'text':
                            if field['multi_valued'] == 'false':
                                term = _marshal_term(value)
                                term_generator.index_text(term, weight)
                                term_generator.index_text(term, weight, prefix)
                                if len(term.split()) == 1:
                                    document.add_term(term, weight)
                                    document.add_term(prefix + term, weight)
                                document.add_value(field['column'], _marshal_value(value))
                            else:
                                for term in value:
                                    term = _marshal_term(term)
                                    term_generator.index_text(term, weight)
                                    term_generator.index_text(term, weight, prefix)
                                    if len(term.split()) == 1:
                                        document.add_term(term, weight)
                                        document.add_term(prefix + term, weight)
                        else:
                            if field['multi_valued'] == 'false':
                                term = _marshal_term(value)
                                if len(term.split()) == 1:
                                    document.add_term(term, weight)
                                    document.add_term(prefix + term, weight)
                                    document.add_value(field['column'], _marshal_value(value))
                            else:
                                for term in value:
                                    term = _marshal_term(term)
                                    if len(term.split()) == 1:
                                        document.add_term(term, weight)
                                        document.add_term(prefix + term, weight)

                document.set_data(pickle.dumps(
                    (obj._meta.app_label, obj._meta.module_name, obj.pk, data),
                    pickle.HIGHEST_PROTOCOL
                ))
                document.add_term(document_id)
                document.add_term(
                    DOCUMENT_CT_TERM_PREFIX + u'%s.%s' %
                    (obj._meta.app_label, obj._meta.module_name)
                )
                database.replace_document(document_id, document)

        except UnicodeDecodeError:
            sys.stderr.write('Chunk failed.\n')
            pass

        finally:
            database.close()

    def remove(self, obj):
        """
        Remove indexes for `obj` from the database.

        We delete all instances of `Q<app_name>.<model_name>.<pk>` which
        should be unique to this object.
        """
        database = self._database(writable=True)
        database.delete_document(DOCUMENT_ID_TERM_PREFIX + get_identifier(obj))
        database.close()

    def clear(self, models=[]):
        """
        Clear all instances of `models` from the database or all models, if
        not specified.

        Optional Arguments:
            `models` -- Models to clear from the database (default = [])

        If `models` is empty, an empty query is executed which matches all
        documents in the database.  Afterwards, each match is deleted.

        Otherwise, for each model, a `delete_document` call is issued with
        the term `XCONTENTTYPE<app_name>.<model_name>`.  This will delete
        all documents with the specified model type.
        """
        database = self._database(writable=True)
        if not models:
            # Because there does not appear to be a "clear all" method,
            # it's much quicker to remove the contents of the `self.path`
            # folder than it is to remove each document one at a time.
            if os.path.exists(self.path):
                shutil.rmtree(self.path)
        else:
            for model in models:
                database.delete_document(
                    DOCUMENT_CT_TERM_PREFIX + '%s.%s' %
                    (model._meta.app_label, model._meta.module_name)
                )
        database.close()

    def document_count(self):
        try:
            return self._database().get_doccount()
        except InvalidIndexError:
            return 0

    @log_query
    def search(self, query, sort_by=None, start_offset=0, end_offset=None,
               fields='', highlight=False, facets=None, date_facets=None,
               query_facets=None, narrow_queries=None, spelling_query=None,
               limit_to_registered_models=True, result_class=None, **kwargs):
        """
        Executes the Xapian::query as defined in `query`.

        Required arguments:
            `query` -- Search query to execute

        Optional arguments:
            `sort_by` -- Sort results by specified field (default = None)
            `start_offset` -- Slice results from `start_offset` (default = 0)
            `end_offset` -- Slice results at `end_offset` (default = None), if None, then all documents
            `fields` -- Filter results on `fields` (default = '')
            `highlight` -- Highlight terms in results (default = False)
            `facets` -- Facet results on fields (default = None)
            `date_facets` -- Facet results on date ranges (default = None)
            `query_facets` -- Facet results on queries (default = None)
            `narrow_queries` -- Narrow queries (default = None)
            `spelling_query` -- An optional query to execute spelling suggestion on
            `limit_to_registered_models` -- Limit returned results to models registered in the current `SearchSite` (default = True)

        Returns:
            A dictionary with the following keys:
                `results` -- A list of `SearchResult`
                `hits` -- The total available results
                `facets` - A dictionary of facets with the following keys:
                    `fields` -- A list of field facets
                    `dates` -- A list of date facets
                    `queries` -- A list of query facets
            If faceting was not used, the `facets` key will not be present

        If `query` is None, returns no results.

        If `INCLUDE_SPELLING` was enabled in the connection options, the
        extra flag `FLAG_SPELLING_CORRECTION` will be passed to the query parser
        and any suggestions for spell correction will be returned as well as
        the results.
        """
        if xapian.Query.empty(query):
            return {
                'results': [],
                'hits': 0,
            }

        database = self._database()

        if result_class is None:
            result_class = SearchResult

        if self.include_spelling is True:
            spelling_suggestion = self._do_spelling_suggestion(database, query, spelling_query)
        else:
            spelling_suggestion = ''

        if narrow_queries is not None:
            query = xapian.Query(
                xapian.Query.OP_AND, query, xapian.Query(
                    xapian.Query.OP_OR, [self.parse_query(narrow_query) for narrow_query in narrow_queries]
                )
            )

        if limit_to_registered_models:
            registered_models = self.build_models_list()

            if len(registered_models) > 0:
                query = xapian.Query(
                    xapian.Query.OP_AND, query,
                    xapian.Query(
                        xapian.Query.OP_OR,  [
                            xapian.Query('%s%s' % (DOCUMENT_CT_TERM_PREFIX, model)) for model in registered_models
                        ]
                    )
                )

        enquire = xapian.Enquire(database)
        if hasattr(settings, 'HAYSTACK_XAPIAN_WEIGHTING_SCHEME'):
            enquire.set_weighting_scheme(xapian.BM25Weight(*settings.HAYSTACK_XAPIAN_WEIGHTING_SCHEME))
        enquire.set_query(query)

        if sort_by:
            sorter = xapian.MultiValueSorter()

            for sort_field in sort_by:
                if sort_field.startswith('-'):
                    reverse = True
                    sort_field = sort_field[1:]  # Strip the '-'
                else:
                    reverse = False  # Reverse is inverted in Xapian -- http://trac.xapian.org/ticket/311
                sorter.add(self._value_column(sort_field), reverse)

            enquire.set_sort_by_key_then_relevance(sorter, True)

        results = []
        facets_dict = {
            'fields': {},
            'dates': {},
            'queries': {},
        }

        if not end_offset:
            end_offset = database.get_doccount() - start_offset

        matches = self._get_enquire_mset(database, enquire, start_offset, end_offset)

        for match in matches:
            app_label, module_name, pk, model_data = pickle.loads(self._get_document_data(database, match.document))
            if highlight:
                model_data['highlighted'] = {
                    self.content_field_name: self._do_highlight(
                        model_data.get(self.content_field_name), query
                    )
                }
            results.append(
                result_class(app_label, module_name, pk, match.percent, **model_data)
            )

        if facets:
            facets_dict['fields'] = self._do_field_facets(results, facets)
        if date_facets:
            facets_dict['dates'] = self._do_date_facets(results, date_facets)
        if query_facets:
            facets_dict['queries'] = self._do_query_facets(results, query_facets)

        return {
            'results': results,
            'hits': self._get_hit_count(database, enquire),
            'facets': facets_dict,
            'spelling_suggestion': spelling_suggestion,
        }

    def more_like_this(self, model_instance, additional_query=None,
                       start_offset=0, end_offset=None,
                       limit_to_registered_models=True, result_class=None, **kwargs):
        """
        Given a model instance, returns a result set of similar documents.

        Required arguments:
            `model_instance` -- The model instance to use as a basis for
                                retrieving similar documents.

        Optional arguments:
            `additional_query` -- An additional query to narrow results
            `start_offset` -- The starting offset (default=0)
            `end_offset` -- The ending offset (default=None), if None, then all documents
            `limit_to_registered_models` -- Limit returned results to models registered in the current `SearchSite` (default = True)

        Returns:
            A dictionary with the following keys:
                `results` -- A list of `SearchResult`
                `hits` -- The total available results

        Opens a database connection, then builds a simple query using the
        `model_instance` to build the unique identifier.

        For each document retrieved(should always be one), adds an entry into
        an RSet (relevance set) with the document id, then, uses the RSet
        to query for an ESet (A set of terms that can be used to suggest
        expansions to the original query), omitting any document that was in
        the original query.

        Finally, processes the resulting matches and returns.
        """
        database = self._database()

        if result_class is None:
            result_class = SearchResult

        query = xapian.Query(DOCUMENT_ID_TERM_PREFIX + get_identifier(model_instance))

        enquire = xapian.Enquire(database)
        enquire.set_query(query)

        rset = xapian.RSet()

        if not end_offset:
            end_offset = database.get_doccount()

        for match in self._get_enquire_mset(database, enquire, 0, end_offset):
            rset.add_document(match.docid)

        query = xapian.Query(
            xapian.Query.OP_ELITE_SET,
            [expand.term for expand in enquire.get_eset(match.document.termlist_count(), rset, XHExpandDecider())],
            match.document.termlist_count()
        )
        query = xapian.Query(
            xapian.Query.OP_AND_NOT, [query, DOCUMENT_ID_TERM_PREFIX + get_identifier(model_instance)]
        )
        if limit_to_registered_models:
            registered_models = self.build_models_list()

            if len(registered_models) > 0:
                query = xapian.Query(
                    xapian.Query.OP_AND, query,
                    xapian.Query(
                        xapian.Query.OP_OR,  [
                            xapian.Query('%s%s' % (DOCUMENT_CT_TERM_PREFIX, model)) for model in registered_models
                        ]
                    )
                )
        if additional_query:
            query = xapian.Query(
                xapian.Query.OP_AND, query, additional_query
            )

        enquire.set_query(query)

        results = []
        matches = self._get_enquire_mset(database, enquire, start_offset, end_offset)

        for match in matches:
            app_label, module_name, pk, model_data = pickle.loads(self._get_document_data(database, match.document))
            results.append(
                result_class(app_label, module_name, pk, match.percent, **model_data)
            )

        return {
            'results': results,
            'hits': self._get_hit_count(database, enquire),
            'facets': {
                'fields': {},
                'dates': {},
                'queries': {},
            },
            'spelling_suggestion': None,
        }

    def parse_query(self, query_string):
        """
        Given a `query_string`, will attempt to return a xapian.Query

        Required arguments:
            ``query_string`` -- A query string to parse

        Returns a xapian.Query
        """
        if query_string == '*':
            return xapian.Query('')  # Match everything
        elif query_string == '':
            return xapian.Query()  # Match nothing

        qp = xapian.QueryParser()
        qp.set_database(self._database())
        qp.set_stemmer(xapian.Stem(self.language))
        qp.set_stemming_strategy(xapian.QueryParser.STEM_SOME)
        qp.add_boolean_prefix('django_ct', DOCUMENT_CT_TERM_PREFIX)

        for field_dict in self.schema:
            qp.add_prefix(
                field_dict['field_name'],
                DOCUMENT_CUSTOM_TERM_PREFIX + field_dict['field_name'].upper()
            )

        vrp = XHValueRangeProcessor(self)
        qp.add_valuerangeprocessor(vrp)

        return qp.parse_query(query_string, self.flags)

    def build_schema(self, fields):
        """
        Build the schema from fields.

        Required arguments:
            ``fields`` -- A list of fields in the index

        Returns a list of fields in dictionary format ready for inclusion in
        an indexed meta-data.
        """
        content_field_name = ''
        schema_fields = [
            {'field_name': ID, 'type': 'text', 'multi_valued': 'false', 'column': 0},
        ]
        column = len(schema_fields)

        for field_name, field_class in sorted(fields.items(), key=lambda n: n[0]):
            if field_class.document is True:
                content_field_name = field_class.index_fieldname

            if field_class.indexed is True:
                field_data = {
                    'field_name': field_class.index_fieldname,
                    'type': 'text',
                    'multi_valued': 'false',
                    'column': column,
                }

                if field_class.field_type in ['date', 'datetime']:
                    field_data['type'] = 'date'
                elif field_class.field_type == 'integer':
                    field_data['type'] = 'long'
                elif field_class.field_type == 'float':
                    field_data['type'] = 'float'
                elif field_class.field_type == 'boolean':
                    field_data['type'] = 'boolean'

                if field_class.is_multivalued:
                    field_data['multi_valued'] = 'true'

                schema_fields.append(field_data)
                column += 1

        return (content_field_name, schema_fields)

    def _do_highlight(self, content, query, tag='em'):
        """
        Highlight `query` terms in `content` with html `tag`.

        This method assumes that the input text (`content`) does not contain
        any special formatting.  That is, it does not contain any html tags
        or similar markup that could be screwed up by the highlighting.

        Required arguments:
            `content` -- Content to search for instances of `text`
            `text` -- The text to be highlighted
        """
        for term in query:
            for match in re.findall('[^A-Z]+', term):  # Ignore field identifiers
                match_re = re.compile(match, re.I)
                content = match_re.sub('<%s>%s</%s>' % (tag, term, tag), content)

        return content

    def _do_field_facets(self, results, field_facets):
        """
        Private method that facets a document by field name.

        Fields of type MultiValueField will be faceted on each item in the
        (containing) list.

        Required arguments:
            `results` -- A list SearchResults to facet
            `field_facets` -- A list of fields to facet on
        """
        facet_dict = {}

        # DS_TODO: Improve this algorithm.  Currently, runs in O(N^2), ouch.
        for field in field_facets:
            facet_list = {}

            for result in results:
                field_value = getattr(result, field)
                if self._multi_value_field(field):
                    for item in field_value:  # Facet each item in a MultiValueField
                        facet_list[item] = facet_list.get(item, 0) + 1
                else:
                    facet_list[field_value] = facet_list.get(field_value, 0) + 1

            facet_dict[field] = facet_list.items()

        return facet_dict

    def _do_date_facets(self, results, date_facets):
        """
        Private method that facets a document by date ranges

        Required arguments:
            `results` -- A list SearchResults to facet
            `date_facets` -- A dictionary containing facet parameters:
                {'field': {'start_date': ..., 'end_date': ...: 'gap_by': '...', 'gap_amount': n}}
                nb., gap must be one of the following:
                    year|month|day|hour|minute|second

        For each date facet field in `date_facets`, generates a list
        of date ranges (from `start_date` to `end_date` by `gap_by`) then
        iterates through `results` and tallies the count for each date_facet.

        Returns a dictionary of date facets (fields) containing a list with
        entries for each range and a count of documents matching the range.

        eg. {
            'pub_date': [
                ('2009-01-01T00:00:00Z', 5),
                ('2009-02-01T00:00:00Z', 0),
                ('2009-03-01T00:00:00Z', 0),
                ('2009-04-01T00:00:00Z', 1),
                ('2009-05-01T00:00:00Z', 2),
            ],
        }
        """
        facet_dict = {}

        for date_facet, facet_params in date_facets.iteritems():
            gap_type = facet_params.get('gap_by')
            gap_value = facet_params.get('gap_amount', 1)
            date_range = facet_params['start_date']
            facet_list = []
            while date_range < facet_params['end_date']:
                facet_list.append((date_range.isoformat(), 0))
                if gap_type == 'year':
                    date_range = date_range.replace(
                        year=date_range.year + int(gap_value)
                    )
                elif gap_type == 'month':
                    if date_range.month + int(gap_value) > 12:
                        date_range = date_range.replace(
                            month=((date_range.month + int(gap_value)) % 12),
                            year=(date_range.year + (date_range.month + int(gap_value)) / 12)
                        )
                    else:
                        date_range = date_range.replace(
                            month=date_range.month + int(gap_value)
                        )
                elif gap_type == 'day':
                    date_range += datetime.timedelta(days=int(gap_value))
                elif gap_type == 'hour':
                    date_range += datetime.timedelta(hours=int(gap_value))
                elif gap_type == 'minute':
                    date_range += datetime.timedelta(minutes=int(gap_value))
                elif gap_type == 'second':
                    date_range += datetime.timedelta(seconds=int(gap_value))

            facet_list = sorted(facet_list, key=lambda n: n[0], reverse=True)

            for result in results:
                result_date = getattr(result, date_facet)
                if result_date:
                    if not isinstance(result_date, datetime.datetime):
                        result_date = datetime.datetime(
                            year=result_date.year,
                            month=result_date.month,
                            day=result_date.day,
                        )
                    for n, facet_date in enumerate(facet_list):
                        if result_date > datetime.datetime(*(time.strptime(facet_date[0], '%Y-%m-%dT%H:%M:%S')[0:6])):
                            facet_list[n] = (facet_list[n][0], (facet_list[n][1] + 1))
                            break

            facet_dict[date_facet] = facet_list

        return facet_dict

    def _do_query_facets(self, results, query_facets):
        """
        Private method that facets a document by query

        Required arguments:
            `results` -- A list SearchResults to facet
            `query_facets` -- A dictionary containing facet parameters:
                {'field': 'query', [...]}

        For each query in `query_facets`, generates a dictionary entry with
        the field name as the key and a tuple with the query and result count
        as the value.

        eg. {'name': ('a*', 5)}
        """
        facet_dict = {}

        for field, query in query_facets.iteritems():
            facet_dict[field] = (query, self.search(self.parse_query(query))['hits'])

        return facet_dict

    def _do_spelling_suggestion(self, database, query, spelling_query):
        """
        Private method that returns a single spelling suggestion based on
        `spelling_query` or `query`.

        Required arguments:
            `database` -- The database to check spelling against
            `query` -- The query to check
            `spelling_query` -- If not None, this will be checked instead of `query`

        Returns a string with a suggested spelling
        """
        if spelling_query:
            if ' ' in spelling_query:
                return ' '.join([database.get_spelling_suggestion(term) for term in spelling_query.split()])
            else:
                return database.get_spelling_suggestion(spelling_query)

        term_set = set()
        for term in query:
            for match in re.findall('[^A-Z]+', term):  # Ignore field identifiers
                term_set.add(database.get_spelling_suggestion(match))

        return ' '.join(term_set)

    def _database(self, writable=False):
        """
        Private method that returns a xapian.Database for use.

        Optional arguments:
            ``writable`` -- Open the database in read/write mode (default=False)

        Returns an instance of a xapian.Database or xapian.WritableDatabase
        """
        if self.path == MEMORY_DB_NAME:
            if not self.inmemory_db:
                self.inmemory_db = xapian.inmemory_open()
            return self.inmemory_db
        if writable:
            database = xapian.WritableDatabase(self.path, xapian.DB_CREATE_OR_OPEN)
        else:
            try:
                database = xapian.Database(self.path)
            except xapian.DatabaseOpeningError:
                raise InvalidIndexError(u'Unable to open index at %s' % self.path)

        return database

    def _get_enquire_mset(self, database, enquire, start_offset, end_offset):
        """
        A safer version of Xapian.enquire.get_mset

        Simply wraps the Xapian version and catches any `Xapian.DatabaseModifiedError`,
        attempting a `database.reopen` as needed.

        Required arguments:
            `database` -- The database to be read
            `enquire` -- An instance of an Xapian.enquire object
            `start_offset` -- The start offset to pass to `enquire.get_mset`
            `end_offset` -- The end offset to pass to `enquire.get_mset`
        """
        try:
            return enquire.get_mset(start_offset, end_offset)
        except xapian.DatabaseModifiedError:
            database.reopen()
            return enquire.get_mset(start_offset, end_offset)

    def _get_document_data(self, database, document):
        """
        A safer version of Xapian.document.get_data

        Simply wraps the Xapian version and catches any `Xapian.DatabaseModifiedError`,
        attempting a `database.reopen` as needed.

        Required arguments:
            `database` -- The database to be read
            `document` -- An instance of an Xapian.document object
        """
        try:
            return document.get_data()
        except xapian.DatabaseModifiedError:
            database.reopen()
            return document.get_data()

    def _get_hit_count(self, database, enquire):
        """
        Given a database and enquire instance, returns the estimated number
        of matches.

        Required arguments:
            `database` -- The database to be queried
            `enquire` -- The enquire instance
        """
        return self._get_enquire_mset(
            database, enquire, 0, database.get_doccount()
        ).size()

    def _value_column(self, field):
        """
        Private method that returns the column value slot in the database
        for a given field.

        Required arguemnts:
            `field` -- The field to lookup

        Returns an integer with the column location (0 indexed).
        """
        for field_dict in self.schema:
            if field_dict['field_name'] == field:
                return field_dict['column']
        return 0

    def _multi_value_field(self, field):
        """
        Private method that returns `True` if a field is multi-valued, else
        `False`.

        Required arguemnts:
            `field` -- The field to lookup

        Returns a boolean value indicating whether the field is multi-valued.
        """
        for field_dict in self.schema:
            if field_dict['field_name'] == field:
                return field_dict['multi_valued'] == 'true'
        return False


class XapianSearchQuery(BaseSearchQuery):
    """
    This class is the Xapian specific version of the SearchQuery class.
    It acts as an intermediary between the ``SearchQuerySet`` and the
    ``SearchBackend`` itself.
    """
    def build_params(self, *args, **kwargs):
        kwargs = super(XapianSearchQuery, self).build_params(*args, **kwargs)

        if self.end_offset is not None:
            kwargs['end_offset'] = self.end_offset - self.start_offset

        return kwargs

    def build_query(self):
        if not self.query_filter:
            query = xapian.Query('')
        else:
            query = self._query_from_search_node(self.query_filter)

        if self.models:
            subqueries = [
                xapian.Query(
                    xapian.Query.OP_SCALE_WEIGHT, xapian.Query('%s%s.%s' % (
                            DOCUMENT_CT_TERM_PREFIX,
                            model._meta.app_label, model._meta.module_name
                        )
                    ), 0  # Pure boolean sub-query
                ) for model in self.models
            ]
            query = xapian.Query(
                xapian.Query.OP_AND, query,
                xapian.Query(xapian.Query.OP_OR, subqueries)
            )

        if self.boost:
            subqueries = [
                xapian.Query(
                    xapian.Query.OP_SCALE_WEIGHT, self._content_field(term, False), value
                ) for term, value in self.boost.iteritems()
            ]
            query = xapian.Query(
                xapian.Query.OP_AND_MAYBE, query,
                xapian.Query(xapian.Query.OP_OR, subqueries)
            )

        return query

    def _query_from_search_node(self, search_node, is_not=False):
        query_list = []

        for child in search_node.children:
            if isinstance(child, SearchNode):
                query_list.append(
                    self._query_from_search_node(child, child.negated)
                )
            else:
                expression, term = child
                field, filter_type = search_node.split_expression(expression)

                # Handle when we've got a ``ValuesListQuerySet``...
                if hasattr(term, 'values_list'):
                    term = list(term)

                if isinstance(term, (list, tuple)):
                    term = [_marshal_term(t) for t in term]
                else:
                    term = _marshal_term(term)

                if field == 'content':
                    query_list.append(self._content_field(term, is_not))
                else:
                    if filter_type == 'contains':
                        query_list.append(self._filter_contains(term, field, is_not))
                    elif filter_type == 'exact':
                        query_list.append(self._filter_exact(term, field, is_not))
                    elif filter_type == 'gt':
                        query_list.append(self._filter_gt(term, field, is_not))
                    elif filter_type == 'gte':
                        query_list.append(self._filter_gte(term, field, is_not))
                    elif filter_type == 'lt':
                        query_list.append(self._filter_lt(term, field, is_not))
                    elif filter_type == 'lte':
                        query_list.append(self._filter_lte(term, field, is_not))
                    elif filter_type == 'startswith':
                        query_list.append(self._filter_startswith(term, field, is_not))
                    elif filter_type == 'in':
                        query_list.append(self._filter_in(term, field, is_not))

        if search_node.connector == 'OR':
            return xapian.Query(xapian.Query.OP_OR, query_list)
        else:
            return xapian.Query(xapian.Query.OP_AND, query_list)

    def _content_field(self, term, is_not):
        """
        Private method that returns a xapian.Query that searches for `value`
        in all fields.

        Required arguments:
            ``term`` -- The term to search for
            ``is_not`` -- Invert the search results

        Returns:
            A xapian.Query
        """
        if ' ' in term:
            if is_not:
                return xapian.Query(
                    xapian.Query.OP_AND_NOT, self._all_query(), self._phrase_query(
                        term.split(), self.backend.content_field_name
                    )
                )
            else:
                return self._phrase_query(term.split(), self.backend.content_field_name)
        else:
            if is_not:
                return xapian.Query(xapian.Query.OP_AND_NOT, self._all_query(), self._term_query(term))
            else:
                return self._term_query(term)

    def _filter_contains(self, term, field, is_not):
        """
        Private method that returns a xapian.Query that searches for `term`
        in a specified `field`.

        Required arguments:
            ``term`` -- The term to search for
            ``field`` -- The field to search
            ``is_not`` -- Invert the search results

        Returns:
            A xapian.Query
        """
        if ' ' in term:
            return self._filter_exact(term, field, is_not)
        else:
            if is_not:
                return xapian.Query(xapian.Query.OP_AND_NOT, self._all_query(), self._term_query(term, field))
            else:
                return self._term_query(term, field)

    def _filter_exact(self, term, field, is_not):
        """
        Private method that returns a xapian.Query that searches for an exact
        match for `term` in a specified `field`.

        Required arguments:
            ``term`` -- The term to search for
            ``field`` -- The field to search
            ``is_not`` -- Invert the search results

        Returns:
            A xapian.Query
        """
        if is_not:
            return xapian.Query(
                xapian.Query.OP_AND_NOT, self._all_query(), self._phrase_query(term.split(), field)
            )
        else:
            return self._phrase_query(term.split(), field)

    def _filter_in(self, term_list, field, is_not):
        """
        Private method that returns a xapian.Query that searches for any term
        of `value_list` in a specified `field`.

        Required arguments:
            ``term_list`` -- The terms to search for
            ``field`` -- The field to search
            ``is_not`` -- Invert the search results

        Returns:
            A xapian.Query
        """
        query_list = []
        for term in term_list:
            if ' ' in term:
                query_list.append(
                    self._phrase_query(term.split(), field)
                )
            else:
                query_list.append(
                    self._term_query(term, field)
                )
        if is_not:
            return xapian.Query(xapian.Query.OP_AND_NOT, self._all_query(), xapian.Query(xapian.Query.OP_OR, query_list))
        else:
            return xapian.Query(xapian.Query.OP_OR, query_list)

    def _filter_startswith(self, term, field, is_not):
        """
        Private method that returns a xapian.Query that searches for any term
        that begins with `term` in a specified `field`.

        Required arguments:
            ``term`` -- The terms to search for
            ``field`` -- The field to search
            ``is_not`` -- Invert the search results

        Returns:
            A xapian.Query
        """
        if is_not:
            return xapian.Query(
                xapian.Query.OP_AND_NOT,
                self._all_query(),
                self.backend.parse_query('%s:%s*' % (field, term)),
            )
        return self.backend.parse_query('%s:%s*' % (field, term))

    def _filter_gt(self, term, field, is_not):
        return self._filter_lte(term, field, is_not=(is_not != True))

    def _filter_lt(self, term, field, is_not):
        return self._filter_gte(term, field, is_not=(is_not != True))

    def _filter_gte(self, term, field, is_not):
        """
        Private method that returns a xapian.Query that searches for any term
        that is greater than `term` in a specified `field`.
        """
        vrp = XHValueRangeProcessor(self.backend)
        pos, begin, end = vrp('%s:%s' % (field, _marshal_value(term)), '*')
        if is_not:
            return xapian.Query(xapian.Query.OP_AND_NOT,
                self._all_query(),
                xapian.Query(xapian.Query.OP_VALUE_RANGE, pos, begin, end)
            )
        return xapian.Query(xapian.Query.OP_VALUE_RANGE, pos, begin, end)

    def _filter_lte(self, term, field, is_not):
        """
        Private method that returns a xapian.Query that searches for any term
        that is less than `term` in a specified `field`.
        """
        vrp = XHValueRangeProcessor(self.backend)
        pos, begin, end = vrp('%s:' % field, '%s' % _marshal_value(term))
        if is_not:
            return xapian.Query(xapian.Query.OP_AND_NOT,
                self._all_query(),
                xapian.Query(xapian.Query.OP_VALUE_RANGE, pos, begin, end)
            )
        return xapian.Query(xapian.Query.OP_VALUE_RANGE, pos, begin, end)

    def _all_query(self):
        """
        Private method that returns a xapian.Query that returns all documents,

        Returns:
            A xapian.Query
        """
        return xapian.Query('')

    def _term_query(self, term, field=None):
        """
        Private method that returns a term based xapian.Query that searches
        for `term`.

        Required arguments:
            ``term`` -- The term to search for
            ``field`` -- The field to search (If `None`, all fields)

        Returns:
            A xapian.Query
        """
        stem = xapian.Stem(self.backend.language)

        if field == 'id':
            return xapian.Query('%s%s' % (DOCUMENT_ID_TERM_PREFIX, term))
        elif field == 'django_ct':
            return xapian.Query('%s%s' % (DOCUMENT_CT_TERM_PREFIX, term))
        elif field:
            stemmed = 'Z%s%s%s' % (
                DOCUMENT_CUSTOM_TERM_PREFIX, field.upper(), stem(term)
            )
            unstemmed = '%s%s%s' % (
                DOCUMENT_CUSTOM_TERM_PREFIX, field.upper(), term
            )
        else:
            stemmed = 'Z%s' % stem(term)
            unstemmed = term

        return xapian.Query(
            xapian.Query.OP_OR,
            xapian.Query(stemmed),
            xapian.Query(unstemmed)
        )

    def _phrase_query(self, term_list, field=None):
        """
        Private method that returns a phrase based xapian.Query that searches
        for terms in `term_list.

        Required arguments:
            ``term_list`` -- The terms to search for
            ``field`` -- The field to search (If `None`, all fields)

        Returns:
            A xapian.Query
        """
        if field:
            return xapian.Query(
                xapian.Query.OP_PHRASE, [
                    '%s%s%s' % (
                        DOCUMENT_CUSTOM_TERM_PREFIX, field.upper(), term
                    ) for term in term_list
                ]
            )
        else:
            return xapian.Query(xapian.Query.OP_PHRASE, term_list)


def _marshal_value(value):
    """
    Private utility method that converts Python values to a string for Xapian values.
    """
    if isinstance(value, datetime.datetime):
        value = _marshal_datetime(value)
    elif isinstance(value, datetime.date):
        value = _marshal_date(value)
    elif isinstance(value, bool):
        if value:
            value = u't'
        else:
            value = u'f'
    elif isinstance(value, float):
        value = xapian.sortable_serialise(value)
    elif isinstance(value, (int, long)):
        value = u'%012d' % value
    else:
        value = force_unicode(value).lower()
    return value


def _marshal_term(term):
    """
    Private utility method that converts Python terms to a string for Xapian terms.
    """
    if isinstance(term, datetime.datetime):
        term = _marshal_datetime(term)
    elif isinstance(term, datetime.date):
        term = _marshal_date(term)
    else:
        term = force_unicode(term).lower()
    return term


def _marshal_date(d):
    return u'%04d%02d%02d000000' % (d.year, d.month, d.day)


def _marshal_datetime(dt):
    if dt.microsecond:
        return u'%04d%02d%02d%02d%02d%02d%06d' % (
            dt.year, dt.month, dt.day, dt.hour,
            dt.minute, dt.second, dt.microsecond
        )
    else:
        return u'%04d%02d%02d%02d%02d%02d' % (
            dt.year, dt.month, dt.day, dt.hour,
            dt.minute, dt.second
        )


class XapianEngine(BaseEngine):
    backend = XapianSearchBackend
    query = XapianSearchQuery
