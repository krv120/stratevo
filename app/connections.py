"""Manager-only configuration diagnostics. No secret values or provider errors returned."""
import os
from app import agent, discovery, suppliers


def status():
    try:
        ai_ready = agent.configured()
    except ValueError:
        ai_ready = False
    return {'ai_configured':ai_ready,'search_configured':discovery.configured(),
            'email_configured':bool(os.environ.get('SMTP_HOST') and os.environ.get('MAIL_FROM')),
            'notice':'Configured is not a connection test. Keys are read from server environment variables; redeploy or restart after changing them.'}


def check(service):
    if service not in ('ai','search'):
        raise suppliers.WorkflowError('Choose ai or search.')
    suppliers.rate_limit('connection-check',5,300)
    if service == 'ai':
        if not status()['ai_configured']:
            return {'ok':False,'message':'Set AI_API_KEY, AI_MODEL and a valid HTTPS AI_BASE_URL, then redeploy.'}
        try:
            answer = agent.provider_request([{'role':'user','content':'Connection test. Reply with OK only.'}],tools=False)
            if not isinstance(answer.get('content'),str) or not answer['content'].strip():
                raise ValueError('Empty answer')
        except agent.ProviderError as error:
            return {'ok':False,'message':str(error),'code':error.code}
        except Exception:
            return {'ok':False,'message':'AI connection failed. Check the endpoint, model access, key, provider billing and hosting outbound access. Secret/provider error details are not shown.'}
        return {'ok':True,'message':'The configured model returned a response. Test a full sourcing conversation next; this basic check does not validate tool calling or answer quality.'}
    result = discovery.discover({'product':'cardboard packaging boxes','volume':100,'unit':'pieces','location':'any','certifications':[]})
    return {'ok':result['status'] in ('online_research','no_match'), 'message':result['message']}
