from django.db import models
import json
from datetime import datetime

# Create your models here.
class Case(models.Model):
    # JSON blob from SCOTUS website
    case_data = models.JSONField()
    term_year = models.IntegerField()
    case_number = models.IntegerField()
    docket_number = models.CharField(max_length=100)

    need_to_send_initial_email = models.BooleanField()
    need_to_send_cfr_email = models.BooleanField()
    consider_for_cfr = models.BooleanField()

    question_presented = models.TextField()

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