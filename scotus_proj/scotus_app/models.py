from django.db import models
import json
from datetime import datetime

# Create your models here.


class Error(models.Model):
    LOADING_NEW_CASE = "LOADING_NEW_CASE"
    LOADING_CFR_CASE = "LOADING_CFR_CASE"
    PARSING_QP = "PARSING_QP"
    MISSING_PETITIONER = "MISSING_PETITIONER"
    choices = (
        (LOADING_NEW_CASE, LOADING_NEW_CASE),
        (LOADING_CFR_CASE, LOADING_CFR_CASE),
        (PARSING_QP, PARSING_QP),
        (MISSING_PETITIONER, MISSING_PETITIONER)
    )
    error_type = models.CharField(max_length=100, choices=choices)
    error_date = models.DateTimeField()
    docket_number = models.CharField(max_length=100)
    error_msg = models.TextField()


class CronHistory(models.Model):
    UPDATE_CASES = "UPDATE_CASES"
    SEND_EMAIL = "SEND_EMAIL"
    choices = (
        (UPDATE_CASES, UPDATE_CASES),
        (SEND_EMAIL, SEND_EMAIL)
    )
    cron_type = models.CharField(max_length=100, choices=choices)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()


class Case(models.Model):
    # TermYear-CaseNumber
    docket_number = models.CharField(max_length=100)

    # We store these too for more efficient lookup
    term_year = models.IntegerField()
    case_number = models.IntegerField()

    # JSON blob from SCOTUS website
    case_data = models.JSONField()

    # QP
    question_presented = models.TextField(null=True)

    # Comms related stuff
    date_initially_added = models.DateTimeField(auto_now_add=True)
    date_cfr_added = models.DateTimeField(null=True)

    # Misc:
    consider_for_cfr = models.BooleanField()

    # Just in case this is heplful
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def docketed_date(self):
        try:
            date_str = json.loads(self.case_data)["DocketedDate"]
            return datetime.strptime(date_str, "%B %d, %Y")
        except:
            return datetime(1900, 1, 1)

    def docketed_date_str(self):
        if self.docketed_date() == datetime(1900, 1, 1):
            return "Unknown Docketed Date"
        else:
            return self.docketed_date().strftime("%B %d, %Y")

    def case_name(self):
        j = json.loads(self.case_data)
        p = json.loads(self.case_data)["PetitionerTitle"]
        if 'RespondentTitle' in j:
            r = json.loads(self.case_data)["RespondentTitle"]
            return "%s v. %s" % (p, r)
        else:
            return p

    def case_url(self):
        return 'https://www.supremecourt.gov/search.aspx?filename=/docket/docketfiles/html/public/%s.html' % self.docket_number

    def petitioner_attorneys(self):
        j = json.loads(self.case_data)
        if 'Petitioner' not in j:
            Error.objects.create(
                error_type=Error.MISSING_PETITIONER,
                error_date=datetime.now(),
                docket_number=self.docket_number,
                error_msg="MISSING PETITIONER"
            )
            return []
        return j["Petitioner"]

    def petitioner_attorney_str(self):
        l = []
        for p in self.petitioner_attorneys():
            name = p["Attorney"]
            if 'Title' not in p or p["Title"] is None:
                l.append(name)
            else:
                l.append("%s (%s)" % (name, p["Title"]))
        return ','.join(l)

    def qp_str(self):
        if self.question_presented is not None:
            return self.question_presented[:1000] + "...[QP SHORTENED DUE TO LENGTH]"
