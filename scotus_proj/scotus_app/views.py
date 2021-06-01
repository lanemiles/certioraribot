from django.shortcuts import render
from .models import Case, CronHistory
from django.db.models import Max
import json

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
    return render(
        request, "scotus_app/detail.html", {"case_dict": case_dict}
    )


def todays_cases(request):
    last_email_sent = CronHistory.objects.filter(
        cron_type=CronHistory.UPDATE_CASES
    ).aggregate(Max("completed_at"))["completed_at__max"]

    initial_email_cases = Case.objects.all()[11:20]#filter(date_initially_added__gt=last_email_sent)
    initial_email_cases = sorted(
        list(initial_email_cases),
        key=lambda x: (x.case_number),
    )

    cfr_email_cases = Case.objects.all()[1:10]#filter(date_cfr_added__gt=last_email_sent)
    cfr_email_cases = sorted(
        list(cfr_email_cases),
        key=lambda x: (x.case_number),
    )

    pretty_str = (
        "There were %i CFRs requested and %i new cert petitions filed today."
        % (len(cfr_email_cases), len(initial_email_cases))
    )

    cfr_data = [
        {
            "docket": x.docket_number,
            "case_url": x.case_url(),
            "case_name": x.case_name(),
            "court_below": x.court_below(),
            "petitioner_attorneys": x.petitioner_attorney_str(),
            "questions_presented": x.qp_str(),
        }    
        for x in cfr_email_cases
    ]

    initial_data = [
        {
            "docket": x.docket_number,
            "case_url": x.case_url(),
            "case_name": x.case_name(),
            "court_below": x.court_below(),
            "petitioner_attorneys": x.petitioner_attorney_str(),
            "questions_presented": x.qp_str(),
        }
        for x in initial_email_cases
    ]

    return render(
        request,
        "scotus_app/email.html",
        {
            "pretty_str": pretty_str,
            "cfr_data": cfr_data,
            "initial_data": initial_data,
        },
    )


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
