"""
Internal info about statuses
of previus parsings.
"""
import binascii
from io import StringIO

from django.db import models

def crc(fname, content=None):
    """
    Calculate CRC-32 checksum of the file contents.
    """

    if content is not None:
        fobj = StringIO(content)
    else:
        fobj = open(fname, 'r')
    value = 0
    for line in fobj:
        value = binascii.crc32(line, value)
    value = value & 0xFFFFFFFF
    fobj.close()
    return "%08x" % value


class FileManager(models.Manager):
    def is_changed(self, path, content=None):
        """
        Compare checksum of the file stored in DB and
        the actual file on the disk.
        `is_changed`  is always true if no info about the file
        is stored in DB.
        """
        
        checksum = crc(path, content)
        try:
            fobj = File.objects.get(path=path)
        except File.DoesNotExist:
            return True
        else:
            return str(fobj.checksum) != checksum

    def save_file(self, path, content=None):
        """
        Save checksum of the file.
        """

        checksum = crc(path, content)
        try:
            fobj = File.objects.get(path=path)
        except File.DoesNotExist:
            fobj = File(path=path)
        fobj.checksum = checksum
        fobj.save()


class File(models.Model):
    """
    Store checksum of processed files.
    """

    path = models.CharField(max_length=100, db_index=True)
    checksum = models.CharField(max_length=8)
    processed = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.path

    objects = FileManager()
