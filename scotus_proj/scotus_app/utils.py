def sort_and_massage_email_data(initial_email_cases, cfr_email_cases):
    initial_email_cases = sorted(
        list(initial_email_cases),
        key=lambda x: (x.case_number),
    )

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

    return {
        "pretty_str": pretty_str,
        "cfr_data": cfr_data,
        "initial_data": initial_data,
    }
