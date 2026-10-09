"""Synthetic TEST ONLY records. Never import into a real research database."""
import json


def write_fixture(path):
    records = [{
        'source_row_id': f'999000-{i}',
        'description_summary': f'SYNTHETIC TEST ONLY Christmas tree 7.5ft flocked warm white model {i}',
        'supplier_as_listed_private':'Yaolan SECRET TEST NAME',
        'product_url':'https://example.invalid/test-only',
        'advertised_price':{'display':'$10–20','min':10,'max':20,'currency_symbol':'$','currency_code':None,'unit_basis':None,'exact_variant_confirmed':False},
        'advertised_moq':{'quantity':10,'unit':'pieces'},
    } for i in range(1,61)]
    path.write_text(json.dumps({'records':records}))
    return path
