import json
with open('C:/Users/azureuser/Desktop/RecoveryIQ/artifacts/policy/recoveriq-sequential-v2/validation-evaluation-v2.json') as f:
    data = json.load(f)
for name, s in data['full_horizon_evaluation']['strategies'].items():
    ep = s.get('episodes')
    rec = s.get('recovered_episodes')
    rate = s.get('recovery_rate')
    net = s.get('simulated_net_recovery_value_minor')
    contacts = s.get('customer_contacts')
    retries = s.get('retry_count')
    hr = s.get('human_reviews')
    pol = s.get('policy_violations')
    print(f'{name}: ep={ep}, rec={rec}, rate={rate}, net={net}, contacts={contacts}, retries={retries}, hr={hr}, pol={pol}')
