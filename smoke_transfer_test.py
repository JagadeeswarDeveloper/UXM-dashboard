import transfer_all as ta

# Mock fetch_table to return small datasets

def fake_fetch(src, table):
    if 'HAPPYSIGNALS' in table:
        return (['Ticket', 'Score'], [('INC1', 7), ('INC2', 8)])
    if 'ESG_METRICS' in table:
        return (['Product Name', 'Manufacturer', 'EPEAT Tier'], [('Latitude 7420', 'Dell', 'Gold')])
    return ([], [])


ta.fetch_table = fake_fetch
res = ta.process_both_from_db('src_conn', 'dst_conn', dry_run=True)
print('SMOKE RESULT:', res)
