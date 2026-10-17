"""Fixed-phase database setup packet; offline generation only."""
import hashlib,json
from pathlib import Path
from infrastructure import migration

ROOT=Path(__file__).resolve().parent
PHASES=('preflight','base','bootstrap','iam','bootstrap002','iam002',
        'bootstrap_extensions','iam_extensions','cleanup_extensions','cleanup002','cleanup','runtime','demo_reference')
OPERATIONS={
 'preflight':['preflight'],'base':['initialize_base'],'bootstrap':['bootstrap'],
 'iam':['migrate','verify'],'bootstrap002':['bootstrap002'],'iam002':['migrate002'],
 'bootstrap_extensions':['bootstrap_extensions'],
 'iam_extensions':['migrate003','migrate004','migrate005','migrate006','verify_extensions'],
 'cleanup_extensions':['cleanup_extensions'],'cleanup002':['cleanup002'],
 'cleanup':['cleanup'],'runtime':['provision_runtime'],'demo_reference':['create_demo_reference']}


def template(phase):
    if phase not in PHASES:raise ValueError('Unknown fixed phase')
    doc=migration.runner_template('preflight')
    del doc['Resources']['RunnerLogs']
    del doc['Resources']['Runner']['DependsOn']
    doc['Description']='Fixed database setup '+phase+'; disabled by default; retained logs reused'
    doc['Parameters']['CodeKey']['AllowedPattern']=r'deployment/migration/[a-f0-9]{64}/fintrust-migration-'+phase+r'\.zip'
    doc['Parameters']['EnableExecution']={'Type':'String','Default':'false','AllowedValues':['false','true']}
    doc['Conditions']={'ExecutionEnabled':{'Fn::Equals':[{'Ref':'EnableExecution'},'true']}}
    runner=doc['Resources']['Runner']['Properties']
    runner['Handler']='migration_runner.'+phase+'_entry.lambda_handler'
    runner['ReservedConcurrentExecutions']={'Fn::If':['ExecutionEnabled',{'Ref':'AWS::NoValue'},0]}
    doc['Resources']['RunnerVersion']['Properties']['Description']='Reviewed fixed database setup '+phase
    return doc


def render():
    ROOT.mkdir(exist_ok=True)
    files={}
    for phase in PHASES:
        path=ROOT/(phase+'.json')
        path.write_text(json.dumps(template(phase),indent=2)+'\n',encoding='utf-8',newline='\n')
        files[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    network=ROOT/'network.json'
    network.write_text(json.dumps(migration.network_template(),indent=2)+'\n',encoding='utf-8',newline='\n')
    files[network.name]=hashlib.sha256(network.read_bytes()).hexdigest()
    result={'status':'PREPARED_NOT_DEPLOYED','application_activation':False,'financial_seed':False,
            'phases':list(PHASES),'operations':OPERATIONS,'template_sha256':files,
            'iam_login_phases':['iam','iam002','iam_extensions'],'resource_scope':'existing private RDS; temporary migration runner/network only'}
    (ROOT/'manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    return result


if __name__=='__main__':print(json.dumps(render(),indent=2))
