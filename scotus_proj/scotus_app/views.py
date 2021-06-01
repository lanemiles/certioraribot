from django.shortcuts import render
from .models import Case
from .utils import sort_and_massage_email_data
import json
from datetime import datetime

# Create your views here.


def index(request):
    cases = Case.objects.all()
    cases_lst = sorted(
        list(cases),
        key=lambda x: (x.docketed_date(), x.term_year, x.case_number),
        reverse=True,
    )[:500]
    return render(
        request,
        "scotus_app/index.html",
        {
            "headline_str": "Welcome to Cert. Bot",
            "base_url_adjustment": "",
            "cases": cases_lst,
        },
    )


def detail(request, docket_number):
    case = Case.objects.get(docket_number=docket_number)
    pretty_json = json.dumps(json.loads(case.case_data), indent=4)
    case_dict = {
        "docket": case.docket_number,
        "qp": case.question_presented,
        "date_initially_added": case.date_initially_added,
        "date_cfr_added": case.date_cfr_added,
        "consider_for_cfr": case.consider_for_cfr,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "docketed_date": case.docketed_date_str(),
        "case_name": case.case_name(),
        "court_below": case.court_below(),
        "case_url": case.case_url(),
        "petitioner_attorneys": case.petitioner_attorney_str(),
        "case_data": pretty_json,
    }
    return render(request, "scotus_app/detail.html", {"case_dict": case_dict})


def test_email(request):
    initial_email_cases = Case.objects.all()[11:20]
    cfr_email_cases = Case.objects.all()[1:10]

    email_data = sort_and_massage_email_data(initial_email_cases, cfr_email_cases)

    return render(request, "scotus_app/email.html", email_data)


def todays_cases(request):
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    initial_email_cases = Case.objects.filter(date_initially_added__gte=start_of_today)
    cfr_email_cases = Case.objects.filter(date_cfr_added__gte=start_of_today)

    email_data = sort_and_massage_email_data(initial_email_cases, cfr_email_cases)

    return render(request, "scotus_app/email.html", email_data)


def cases_to_consider_for_cfr(request):
    cases = Case.objects.filter(consider_for_cfr=True, need_to_send_cfr_email=False)
    cases_lst = sorted(
        list(cases),
        key=lambda x: (x.docketed_date(), x.term_year, x.case_number),
        reverse=True,
    )
    return render(
        request,
        "scotus_app/index.html",
        {
            "headline_str": "Cases Still Considering for CFR",
            "base_url_adjustment": "../",
            "cases": cases_lst,
        },
    )


def cases_with_cfr(request):
    cases = Case.objects.all()
    cases_with_cfr = []
    for c in cases:
        try:
            if "Response Requested" in str(
                json.loads(c.case_data)["ProceedingsandOrder"]
            ):
                cases_with_cfr.append(c)
        except Exception:
            continue
    cases_lst = sorted(
        list(cases_with_cfr),
        key=lambda x: (x.docketed_date(), x.term_year, x.case_number),
        reverse=True,
    )
    return render(
        request,
        "scotus_app/index.html",
        {
            "headline_str": "Cases With a CFR",
            "base_url_adjustment": "../",
            "cases": cases_lst,
        },
    )
