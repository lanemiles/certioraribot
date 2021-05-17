from django.shortcuts import render
from django.http import HttpResponse
import requests
import json
from .models import Case
from django.shortcuts import render
import queue
from django.db.models import Max
import smtplib
import datetime
from email.mime.text import MIMEText
from django.template.loader import render_to_string
import pdfplumber
import re
import time


# Create your views here.
def index(request):
    cases = Case.objects.all()
    cases_lst = sorted(list(cases), key = lambda x: x.docketed_date(), reverse=True )
    return render(request, 'scotus_app/index.html', { "cases": cases_lst })

def detail(request, docket_number):
    case = Case.objects.get(docket_number = docket_number)
    pretty_json = json.dumps(json.loads(case.case_data), indent = 4)
    return render(request, 'scotus_app/detail.html', { "case": case, "pretty_json": pretty_json })

def update_cases(request):

    # Get the max term year
    term_year = Case.objects.aggregate(Max('term_year'))['term_year__max']
    if term_year is None:
        term_year = 20

    # Get the max paid and free case numbers
    SWITCH_POINT = 5000
    max_paid_case_num =  Case.objects.filter(term_year = term_year, case_number__lte = SWITCH_POINT).aggregate(Max('case_number'))['case_number__max']
    max_free_case_num = Case.objects.filter(term_year = term_year, case_number__gte = SWITCH_POINT + 1).aggregate(Max('case_number'))['case_number__max']

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
        curr_case_num = case_nums_to_explore.get()
        docket_num = "%s-%s" % (term_year, curr_case_num)
        url = "https://www.supremecourt.gov/RSS/Cases/JSON/%s.json" % (docket_num)
        print("Checking: %s" % docket_num)
        data = requests.get(url)
        if data is not None and data.status_code == 200:
            json_data = json.loads(data.text)
            Case.objects.create(
                term_year = term_year,
                case_number = curr_case_num,
                docket_number = docket_num,
                case_data = json.dumps(json_data),
                need_to_send_initial_email = True,
                need_to_send_cfr_email = False,
                consider_for_cfr = should_consider_for_cfr(json_data),
                question_presented = get_qp(json_data)
            )
            print("Found: %s" % docket_num)
            case_nums_to_explore.put(curr_case_num + 1)
        else:
            print("Did not find: %s" % docket_num)

    # Explore for new CFRs
    dockets_to_explore = ["%s-%s" % (x.term_year, x.case_number) for x in list(Case.objects.filter(consider_for_cfr = True))]
    for docket in dockets_to_explore:
        url = "https://www.supremecourt.gov/RSS/Cases/JSON/%s.json" % (docket_num)
        print("Checking: %s" % docket_num)
        data = requests.get(url)
        if data is not None and data.status_code == 200:
            json_data = json.loads(data.text)
            case = Case.objects.get(docket_number = docket)

            has_cfr = now_has_cfr(json_data)
            consider_for_cfr = should_consider_for_cfr(json_data)

            if has_cfr:
                print("Found CFR: %s" % docket)
                case.need_to_send_cfr_email = True
                case.consider_for_cfr = False
            elif not consider_for_cfr:
                print("Past CFR: %s" % docket)
                case.consider_for_cfr = False
            else:
                print("No change: %s" % docket)
            case.save()

    return HttpResponse("Updated cases!")

def download_pdf(url, file_name):
    p = requests.get(url)
    with open(file_name, "wb") as f:
        f.write(p.content)

def parse_pdf(file_name):
    pdf = pdfplumber.open(file_name)
    pages = [p.extract_text() for p in pdf.pages]

    # Find the end of the QP by finding the page that PARTIES or CONTENTS is on, and go back one
    next_page = None
    for idx, txt in enumerate(pages):
        if 'PARTIES' in txt or 'CONTENTS' in txt:
            next_page = idx
            break

    if next_page is None:
        return "COULT NOT PARSE QP FROM PDF."

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
    pages[-1] = re.sub('(?=.*)[^.?!]+$', '', pages[-1])

    qp_str = ' '.join(pages)

    # Now final cleaning and shortening
    qp_str = re.sub('\s{2}', ' ', qp_str)

    if len(qp_str) > 1000:
        qp_str = qp_str[:1000]
        qp_str = "%s...[QP CUT OFF DUE TO LENGTH]" % qp_str

    pdf.close()

    return qp_str

def get_qp(json_data):
    try:
        url = get_qp_url(json_data)
        if url is None:
            return None

        file_loc = "tmp.pdf"
        download_pdf(url, file_loc)
        return parse_pdf(file_loc)
    except:
        return None


def get_qp_url(json_data):
    url = None
    proceedings = json_data["ProceedingsandOrder"]
    for p in proceedings:
        if 'Petition for a writ' in p["Text"]:
            if 'Links' in p:
                links = p["Links"]
                for l in links:
                    if l["Description"] == 'Petition':
                        url = l["DocumentUrl"]
    return url
    

def now_has_cfr(json_data):
    proceedings = str(json_data["ProceedingsandOrder"])
    return 'Response Requested' in proceedings

def should_consider_for_cfr(json_data):
    proceedings = str(json_data["ProceedingsandOrder"])
    past_cfr_strs = ['Brief of respondent', 'Memorandum of respondent', 'Petition DENIED']
    past_cfr = any([s in proceedings for s in past_cfr_strs])
    return not past_cfr

def todays_cases(request):
    initial_email_cases = Case.objects.filter(need_to_send_initial_email = True)
    cfr_email_cases = Case.objects.filter(need_to_send_cfr_email = True)

    pretty_str = "There were %i CFRs requested and %i new cert petitions filed today." % (len(cfr_email_cases), len(initial_email_cases))
    
    cfr_data = [{
        "url": x.case_url(),
        "docket": x.docket_number
    } for x in cfr_email_cases]

    initial_data = [{
        "docket": x.docket_number,
        "case_url": x.case_url(),
        "case_name": x.case_name(),
        "petitioner_attorneys": x.petitioner_attorney_str(),
        "questions_presented": x.question_presented
    } for x in initial_email_cases]

    return render(request, 'scotus_app/email.html', {
        "pretty_str": pretty_str,
        "cfr_data": cfr_data,
        "initial_data": initial_data,
    })

def send_daily_email(request):
    initial_email_cases = Case.objects.filter(need_to_send_initial_email = True)
    cfr_email_cases = Case.objects.filter(need_to_send_cfr_email = True)

    pretty_str = "There were %i CFRs requested and %i new cert petitions filed today." % (len(cfr_email_cases), len(initial_email_cases))
    
    cfr_data = [{
        "url": x.case_url(),
        "docket": x.docket_number
    } for x in cfr_email_cases]

    initial_data = [{
        "docket": x.docket_number,
        "case_url": x.case_url(),
        "case_name": x.case_name(),
        "petitioner_attorneys": x.petitioner_attorney_str(),
        "questions_presented": x.question_presented
    } for x in initial_email_cases]

    server = smtplib.SMTP('smtp.gmail.com:587')
    server.starttls()
    server.ehlo()
    server.login('certioraribot@gmail.com', 'scotus123')

    fromx = 'certioraribot@gmail.com'
    subject = '[Certiorari Bot] New Cert Petitions for %s' % datetime.datetime.now().strftime("%B %d, %Y")
    html = render_to_string('scotus_app/email.html', {
        "pretty_str": pretty_str,
        "cfr_data": cfr_data,
        "initial_data": initial_data,
    })

    msg = MIMEText(html, 'html')
    msg['Subject'] = subject
    msg['From'] = fromx

    to_emails = ['lmiles1234@gmail.com', 'martinsicilian@gmail.com']
    for to in to_emails:
        msg['To'] = to
        server.sendmail(fromx, to, msg.as_string())
    
    server.quit()

    for c in initial_email_cases:
        c.need_to_send_initial_email = False
        c.save()

    for c in cfr_email_cases:
        c.need_to_send_cfr_email = False
        c.save()

    return HttpResponse("Emails sent!")
