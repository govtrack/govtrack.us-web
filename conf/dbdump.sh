#!/bin/bash

BACKUP_DIR=/home/govtrack/backup

mkdir -p $BACKUP_DIR

function backup() {
    # Limit line length to the minimum mysqldump will accept.
    FN=$1 && shift
    echo $@...
    mysqldump $(./manage.py dbparams) --no-tablespaces --net_buffer_length=4096 --default-character-set=utf8mb4 $@ \
      | gzip > $BACKUP_DIR/$(date --iso-8601 | sed s/-//g)-$FN.sql.gz
}

TABLE_LIST="
auth_group
auth_group_permissions
auth_message
auth_permission
auth_user
auth_user_groups
auth_user_user_permissions
django_admin_log
django_content_type
django_migrations
django_session
django_site
emailverification_bouncedemail
emailverification_ping
emailverification_record
events_subscriptionlist
events_subscriptionlist_trackers
poll_and_call_calllog
poll_and_call_issue
poll_and_call_issue_positions
poll_and_call_issueposition
poll_and_call_relatedbill
poll_and_call_userposition
registration_authrecord
userpanels_panel
userpanels_panel_admins
userpanels_panelinvitation
userpanels_panelmembership
website_blogpost
website_campaignsupporter
website_communityinterest
website_community
website_communitymessageboard
website_communitymessage
website_mediumpost
website_paypalpayment
website_reaction
website_req
website_usergroupsignup
website_userposition
website_userprofile
"

backup userdata $TABLE_LIST

export TABLE_LIST="
bill_amendment
bill_bill
bill_bill_committees
bill_bill_terms
bill_billlink
bill_billsummary
bill_billterm
bill_billterm_subterms
bill_cosponsor
bill_relatedbill
committee_committee
committee_committeemeeting
committee_committeemeeting_bills
committee_committeemember
events_event
events_feed
oversight_oversightrelevantbill
oversight_oversightrelevantcommittee
oversight_oversightrelevantperson
oversight_oversighttopic
oversight_oversighttopic_related_oversight_topics
oversight_oversightupdate
person_person
person_personrole
stakeholder_billposition
stakeholder_post
stakeholder_stakeholder
stakeholder_stakeholder_admins
stakeholder_voteposition
vote_vote
vote_voteoption
vote_voter
vote_votesummary
"

backup legdata $TABLE_LIST

