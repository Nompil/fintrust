"""Two labelled demonstration account references; never copy or seed transactions."""
from . import common,config

ACCOUNTS=('20000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000002')


def create(conn,op):
    if op!='create_demo_reference':raise common.Refused('operation_not_allowed')
    with conn.cursor() as cur:
        common.setup(cur,read_only=False);common.session_check(cur,config.MASTER)
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('fintrust-demo-reference:public'))")
        cur.execute("SELECT count(*) FROM pg_roles WHERE rolname IN ('fintrust_scoring_dev','fintrust_api_dev','fintrust_report_dev')")
        if cur.fetchone()!=(3,):raise common.Refused('runtime_setup_required')
        cur.execute('GRANT fintrust_transactions_owner TO fintrust_admin WITH SET TRUE,INHERIT TRUE,ADMIN FALSE')
        for table in config.TABLES:
            cur.execute('SELECT count(*) FROM public.'+table)
            if cur.fetchone()!=(0,):raise common.Refused('demo_reference_requires_empty_application_data')
        for number,account in enumerate(ACCOUNTS,1):
            customer='10000000-0000-4000-8000-00000000000'+str(number)
            cur.execute("INSERT INTO public.customers(customer_id,full_name,id_number,kyc_status) VALUES(%s,%s,%s,'verified')",
                        (customer,'FinTrust Demonstration Customer '+str(number),'FT-DEMO-000'+str(number)))
            cur.execute("INSERT INTO public.accounts(account_id,customer_id,account_type,balance,status) VALUES(%s,%s,'savings',0,'active')",(account,customer))
        cur.execute('SELECT count(*) FROM public.transactions')
        if cur.fetchone()!=(0,):raise common.Refused('demo_reference_financial_row_postcheck_failed')
        cur.execute('GRANT fintrust_transactions_owner TO fintrust_admin WITH SET FALSE,INHERIT FALSE,ADMIN FALSE')
    return {'synthetic_reference_accounts':list(ACCOUNTS),'opening_balances_zero':True,
            'transaction_rows_created':0,'real_customer_data_used':False},True
