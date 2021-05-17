from django.shortcuts import render
from .models import Case
import json

# Create your views here.
def index(request):
    cases = Case.objects.all()
    cases_lst = sorted(list(cases), key = lambda x: (x.docketed_date(), x.term_year, x.case_number), reverse=True )
    return render(request, 'scotus_app/index.html', { "cases": cases_lst })

def detail(request, docket_number):
    case = Case.objects.get(docket_number = docket_number)
    pretty_json = json.dumps(json.loads(case.case_data), indent = 4)
    return render(request, 'scotus_app/detail.html', { "case": case, "pretty_json": pretty_json })
    

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