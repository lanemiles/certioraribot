from .models import Case, CronHistory, Error
import pdfplumber
import re
import queue
from django.db.models import Max
import requests
import json
import time
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from django.template.loader import render_to_string


class UpdateCases:
    def do(self):
        print("Starting update cases for %s" % datetime.today().strftime("%D"))
        cron_history = CronHistory(
            cron_type=CronHistory.UPDATE_CASES, started_at=datetime.now()
        )
        self.update_new_dockets()
        self.update_cfr_dockets()
        cron_history.completed_at = datetime.now()
        cron_history.save()

    def update_new_dockets(self):
        # Get the max term year
        term_year = Case.objects.aggregate(Max("term_year"))["term_year__max"]
        if term_year is None:
            term_year = 20

        # Get the max paid and free case numbers
        SWITCH_POINT = 5000
        max_paid_case_num = Case.objects.filter(
            term_year=term_year, case_number__lte=SWITCH_POINT
        ).aggregate(Max("case_number"))["case_number__max"]
        max_free_case_num = Case.objects.filter(
            term_year=term_year, case_number__gte=SWITCH_POINT + 1
        ).aggregate(Max("case_number"))["case_number__max"]

        if max_paid_case_num is None:
            max_paid_case_num = 0
        if max_free_case_num is None:
            max_free_case_num = SWITCH_POINT

        # Generate starting points
        case_nums_to_explore = queue.Queue()
        case_nums_to_explore.put(max_paid_case_num + 1)
        case_nums_to_explore.put(max_free_case_num + 1)

        # Explore for new dockets
        while not case_nums_to_explore.empty():
            time.sleep(0.5)
            curr_case_num = case_nums_to_explore.get()
            self.explore_new_docket(term_year, curr_case_num, case_nums_to_explore)

    def update_cfr_dockets(self):
        # Explore for new CFRs
        dockets_to_explore = [
            x.docket_number for x in list(Case.objects.filter(consider_for_cfr=True))
        ]
        for docket in dockets_to_explore:
            time.sleep(0.5)
            self.explore_cfr_docket(docket)

    def explore_new_docket(self, term_year, case_number, q):
        try:
            docket_num = "%s-%s" % (term_year, case_number)
            print("Exploring %s" % docket_num)
            url = "https://www.supremecourt.gov/RSS/Cases/JSON/%s.json" % (docket_num)
            data = requests.get(url)
            if data is not None and data.status_code == 200:
                json_data = json.loads(data.text)
                Case.objects.create(
                    term_year=term_year,
                    case_number=case_number,
                    docket_number=docket_num,
                    case_data=json.dumps(json_data),
                    question_presented=self.get_qp(json_data, docket_num),
                    consider_for_cfr=self.should_consider_for_cfr(json_data),
                )
                print("Found: %s" % docket_num)
                q.put(case_number + 1)
            else:
                print("Did not find: %s" % docket_num)
        except Exception as e:
            Error.objects.create(
                error_type=Error.LOADING_NEW_CASE,
                error_date=datetime.now(),
                docket_number=docket_num,
                error_msg=str(e),
            )
            print("SOMETHING WENT WRONG TRYING TO CHECK DOCKET %s" % e)

    def explore_cfr_docket(self, docket_num):
        try:
            url = "https://www.supremecourt.gov/RSS/Cases/JSON/%s.json" % (docket_num)
            print("Checking: %s" % docket_num)
            data = requests.get(url)
            if data is not None and data.status_code == 200:
                json_data = json.loads(data.text)
                case = Case.objects.get(docket_number=docket_num)

                has_cfr = self.now_has_cfr(json_data)
                consider_for_cfr = self.should_consider_for_cfr(json_data)

                if has_cfr:
                    print("Found CFR: %s" % docket_num)
                    case.date_cfr_added = datetime.now()
                    case.consider_for_cfr = False
                elif not consider_for_cfr:
                    print("Past CFR: %s" % docket_num)
                    case.consider_for_cfr = False
                else:
                    print("No change: %s" % docket_num)
                case.save()
        except Exception as e:
            Error.objects.create(
                error_type=Error.LOADING_CFR_CASE,
                error_date=datetime.now(),
                docket_number=docket_num,
                error_msg=str(e),
            )
            print("SOMETHING WENT WRONG TRYING TO CHECK FOR CFR %s" % e)

    def download_pdf(self, url, file_name):
        p = requests.get(url)
        with open(file_name, "wb") as f:
            f.write(p.content)

    def parse_pdf(self, file_name):
        pdf = pdfplumber.open(file_name)
        pages = [p.extract_text() for p in pdf.pages]

        # Find the end of the QP by finding the page that PARTIES or CONTENTS is on, and go back one
        next_page = None
        for idx, txt in enumerate(pages):
            if "PARTIES" in txt or "CONTENTS" in txt:
                next_page = idx
                break

        if next_page is None:
            raise Exception("COULD NOT FIND END OF QP!")

        # Trim to just pages we care about, QP always starts on page 2
        pages = pages[1:next_page]

        # Clean up the spaces
        pages = [p.replace("\n", "") for p in pages]

        # Now, remove everything up-to-and-including PRESENTED on the first page
        start_idx = pages[0].find("PRESENTED") + len("PRESENTED")
        pages[0] = pages[0][start_idx:]

        # And the beginning whitespace
        pages[0] = pages[0].lstrip()

        # Now, remove everything after the final punctuation mark on the last page.
        pages[-1] = re.sub("(?=.*)[^.?!]+$", "", pages[-1])

        qp_str = " ".join(pages)

        # Now final cleaning and shortening
        qp_str = re.sub("\s{2}", " ", qp_str)

        pdf.close()

        return qp_str

    def get_qp(self, json_data, docket_num):
        try:
            url = self.get_qp_url(json_data)
            if url is None:
                raise Exception("FAILED TO FIND URL")

            file_loc = "tmp.pdf"
            self.download_pdf(url, file_loc)
            return self.parse_pdf(file_loc)
        except Exception as e:
            print("FAILED TO GET THE QP")
            Error.objects.create(
                error_type=Error.PARSING_QP,
                error_date=datetime.now(),
                docket_number=docket_num,
                error_msg=str(e),
            )
            return None

    def get_qp_url(self, json_data):
        url = None
        proceedings = json_data["ProceedingsandOrder"]
        for p in proceedings:
            if "Petition for a writ" in p["Text"]:
                if "Links" in p:
                    links = p["Links"]
                    for l in links:
                        if l["Description"] == "Petition":
                            url = l["DocumentUrl"]
        return url

    def now_has_cfr(self, json_data):
        proceedings = str(json_data["ProceedingsandOrder"])
        return "Response Requested" in proceedings

    def should_consider_for_cfr(self, json_data):
        proceedings = str(json_data["ProceedingsandOrder"])
        past_cfr_strs = [
            "Brief of respondent",
            "Memorandum of respondent",
            "Petition DENIED",
        ]
        past_cfr = any([s in proceedings for s in past_cfr_strs])
        return not past_cfr


class SendEmail:
    def do(self):
        print("Starting email job for %s" % datetime.today().strftime("%D"))
        cron_history = CronHistory(
            cron_type=CronHistory.SEND_EMAIL, started_at=datetime.now()
        )

        last_email_sent = CronHistory.objects.filter(
            cron_type=CronHistory.SEND_EMAIL
        ).aggregate(Max("completed_at"))["completed_at__max"]

        initial_email_cases = Case.objects.filter(
            date_initially_added__gt=last_email_sent
        )
        cfr_email_cases = Case.objects.filter(date_cfr_added__gt=last_email_sent)

        pretty_str = (
            "There were %i CFRs requested and %i new cert petitions filed today."
            % (len(cfr_email_cases), len(initial_email_cases))
        )

        cfr_data = [
            {"url": x.case_url(), "docket": x.docket_number} for x in cfr_email_cases
        ]

        initial_data = [
            {
                "docket": x.docket_number,
                "case_url": x.case_url(),
                "case_name": x.case_name(),
                "petitioner_attorneys": x.petitioner_attorney_str(),
                "questions_presented": x.qp_str(),
            }
            for x in initial_email_cases
        ]

        server = smtplib.SMTP("smtp.gmail.com:587")
        server.starttls()
        server.ehlo()
        server.login("certioraribot@gmail.com", "scotus123")

        fromx = "certioraribot@gmail.com"
        subject = (
            "[Certiorari Bot] New Cert Petitions for %s"
            % datetime.now().strftime("%B %d, %Y")
        )
        html = render_to_string(
            "scotus_app/email.html",
            {
                "pretty_str": pretty_str,
                "cfr_data": cfr_data,
                "initial_data": initial_data,
            },
        )

        msg = MIMEText(html, "html")
        msg["Subject"] = subject
        msg["From"] = fromx

        to_emails = ["lmiles1234@gmail.com", "martinsicilian@gmail.com"]
        for to in to_emails:
            msg["To"] = to
            server.sendmail(fromx, to, msg.as_string())

        server.quit()

        cron_history.completed_at = datetime.now()
        cron_history.save()
