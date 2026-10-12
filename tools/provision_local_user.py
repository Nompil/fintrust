"""Enroll an existing local user without printing credentials or altering RBAC."""
import argparse,getpass,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
def main():
    p=argparse.ArgumentParser();p.add_argument('--username',required=True);p.add_argument('--registry',required=True);args=p.parse_args()
    os.environ['FINTRUST_MODE']='local';os.environ['FINTRUST_AUTH_FILE']=str(Path(args.registry).resolve())
    value=getpass.getpass('Unique random local credential (hidden): ')
    if value!=getpass.getpass('Confirm credential (hidden): '):raise ValueError('Credentials differ')
    from fintrust.local_users import provision_credential
    result=provision_credential(args.username,value)
    print('Credential provisioned for '+result['username']+'; role and account scope unchanged.')
if __name__=='__main__':main()
