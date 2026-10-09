"""Normalize manually reviewed research TSV. Never infers missing supplier facts."""
import argparse
import csv
import json
import re
from decimal import Decimal
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.catalog import private_path


def normalize(path, batch):
    path=private_path(path)
    if not re.fullmatch(r'[0-9]+',batch):raise ValueError('Numeric batch ID required')
    records=[]
    with path.open(encoding='utf-8-sig', newline='') as source:
        rows = list(csv.DictReader(source,delimiter='\t'))
    for row in rows:
        prices=row['price_eur'].split('-')
        if not 1<=len(prices)<=2 or any(not re.fullmatch(r'\d+(?:\.\d{1,4})?',p) for p in prices):raise ValueError('Review price format')
        if Decimal(prices[0])>Decimal(prices[-1]):raise ValueError('Inverted price range')
        records.append({
          'source_row_id':batch+'-'+str(int(row['row'])),
          'description_summary':row['description_summary'],
          'supplier_as_listed_private':None,
          'advertised_price':{'display':'€'+row['price_eur'],'min':prices[0],'max':prices[-1],'currency_symbol':'€','currency_code':'EUR','unit_basis':None,'exact_variant_confirmed':False},
          'advertised_moq':{'quantity':int(row['moq_number']),'unit':None},
          'matrix':{'category':row['category'],'location':None,'lead_time_days':None,'certifications_claimed':[s.strip() for s in row['certification_claims'].split(';') if s.strip()], 'certifications_verified':[], 'target_price':None},
          'verification_status':'unverified_user_supplied_listing',
          'product_url':None,'scraped_at':None,
          'provenance':{'method':'Manually transcribed summaries from user-pasted text; not a lossless raw scrape','batch':batch,'moq_note':'Number appears immediately before MOQ; no unit supplied','price_note':'Manually separated advertised price from concatenated title; variant and unit not established'},
        })
    result={'schema_version':2,'source':'User-pasted Alibaba research; manually reviewed partial transcription','records':records}
    output=path.with_suffix('.json');output.write_text(json.dumps(result,ensure_ascii=False,indent=2));output.chmod(0o600)
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('path');parser.add_argument('--batch',required=True);args=parser.parse_args()
    print(normalize(args.path,args.batch))
