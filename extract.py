import json
d = json.load(open('artifacts/policy/recoveriq-sequential-v2/validation-evaluation-v2.json', encoding='utf-8'))
strategies = d['full_horizon_evaluation']['strategies']
for name, st in strategies.items():
    net = st.get('simulated_net_recovery_value_minor', 0) / 100.0
    rec = st.get('recovered_episodes', 0)
    rate = st.get('recovery_rate', 0.0)
    interventions = st.get('total_interventions', 0)
    retries = st.get('retry_count', 0)
    contacts = st.get('customer_contacts', 0)
    violations = st.get('policy_violations', 0)
    print(f"{name} | {rec} | {rate:.4%} | {net:,.2f} | {retries} | {contacts} | {violations}")
