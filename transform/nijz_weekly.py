import glob
import logging
import os
import time
from datetime import datetime

import pandas as pd

from country_codes import get_county_code
from utils import sha1sum


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

covid_data_path = os.getenv('COVID_DATA_PATH')
assert covid_data_path, 'COVID_DATA_PATH env variable must be set. (The location of the COVID-DATA folder)'

SOURCE_FILE_INFECTED = max(glob.glob(os.path.join(covid_data_path, 'EPI') + '/tedenski_prikaz_okuzeni*.xlsx'))  # take latest
logger.info(f'SOURCE_FILE okuzeni: {SOURCE_FILE_INFECTED}')
SOURCE_FILE_DECEASED = max(glob.glob(os.path.join(covid_data_path, 'EPI') + '/tedenski_prikaz_umrli*.xlsx'))  # take latest
logger.info(f'SOURCE_FILE umrli: {SOURCE_FILE_DECEASED}')
CSV_FOLDER = os.path.join(os.path.dirname(__file__), '../csv')


df_d_1 = pd.read_excel(io=SOURCE_FILE_DECEASED, sheet_name='Tabela 1', engine='openpyxl', skiprows=[0], skipfooter=2)
df_d_1.drop('Ostalo prebivalstvo', axis='columns', inplace=True)
df_d_1.rename(columns={'Leto in ISO teden izvida': 'week', 'Oskrbovanci': 'week.rhoccupant', 'SKUPAJ': 'week.confirmed'}, inplace=True)
df_d_1.set_index('week', inplace=True)
df_d_1 = df_d_1.replace({0: None}).astype('Int64')

df_d_2 = pd.read_excel(io=SOURCE_FILE_DECEASED, sheet_name='Tabela 2', engine='openpyxl', skiprows=[0], skipfooter=2)
df_d_2.drop('Ostalo prebivalstvo', axis='columns', inplace=True)
df_d_2.rename(columns={'Leto in ISO teden smrti': 'week', 'Oskrbovanci': 'week.deceased.rhoccupant', 'SKUPAJ': 'week.deceased'}, inplace=True)
df_d_2.set_index('week', inplace=True)
df_d_2 = df_d_2.replace({0: None}).astype('Int64')

df_i_1 = pd.read_excel(io=SOURCE_FILE_INFECTED, sheet_name='Tabela 1', engine='openpyxl', skiprows=[0, 2], skipfooter=1) \
    .rename(columns={
        'Teden': 'week',
        'Skupaj': 'week.investigated',
        'lokalni vir': 'week.src.local',
        'neznani vir': 'week.src.unknown',
        'importiran': 'week.src.import',
        'importiran cluster': 'week.src.import-related',
    }).set_index('week').drop('ni podatka', axis='columns')
df_i_1 = df_i_1.replace({0: None}).astype('Int64')

df_i_2 = pd.read_excel(io=SOURCE_FILE_INFECTED, sheet_name='Tabela 2', engine='openpyxl', skiprows=[0, 2], skipfooter=1) \
    .rename(columns={
        'Teden': 'week',
        'družina, skupno gospodinjstvo': 'week.loc.family',
        'delovno mesto': 'week.loc.work',
        'vzgojno-izobraževalna ustanova': 'week.loc.school',
        'bolnišnica': 'week.loc.hospital',
        'druga zdravstvena ustanova': 'week.loc.otherhc',
        'DSO/SVZ': 'week.loc.rh',
        'zapor': 'week.loc.prison',
        'javni prevoz': 'week.loc.transport',
        'trgovina': 'week.loc.shop',
        'gostinski obrat': 'week.loc.restaurant',
        'športna dejavnost (zaprt prostor)': 'week.loc.sport',
        'zasebno druženje': 'week.loc.gathering_private',
        'organizirano druženje': 'week.loc.gathering_organized',
        'drugo': 'week.loc.other',
        'neznano': 'week.loc.unknown'
    }).drop('Skupaj', axis='columns').set_index('week')
df_i_2 = df_i_2.replace({0: None}).astype('Int64')

df_i_3 = pd.read_excel(io=SOURCE_FILE_INFECTED, sheet_name='Tabela 3', engine='openpyxl', skiprows=[0, 2], skipfooter=1).transpose()[:-1]
df_i_3.columns = df_i_3.iloc[0]
df_i_3 = df_i_3[1:]
df_i_3.index.rename('date', inplace=True)
df_i_3 = df_i_3.rename(mapper=lambda x: f'week.from.{get_county_code(x)}', axis='columns')
df_i_3 = df_i_3.replace({0: None}).astype('Int64')

df_i_4 = pd.read_excel(io=SOURCE_FILE_INFECTED, sheet_name='Tabela 4', engine='openpyxl', skiprows=[0, 2], skipfooter=1).rename(columns={
        'Teden': 'week',
        'Zdravstveni delavec': 'week.healthcare',
    }).set_index('week')
df_i_4 = df_i_4.replace({0: None}).astype('Int64')

# source quarantine data from archival CSV
df_quarantine = pd.read_csv(os.path.join(CSV_FOLDER, 'stats-weekly-archive.csv'), index_col='week')
df_quarantine = df_quarantine[['week.sent_to.quarantine', 'week.src.quarantine']]
df_quarantine = df_quarantine.replace({0: None}).astype('Int64')

merged = df_d_1.join(df_d_2).join(df_i_1).join(df_i_2).join(df_i_3).join(df_i_4).join(df_quarantine)

week_dates = {'week': [], 'date': [], 'date.to': []}
for x in merged.index:
    year, week = x.split('-')
    week_start = datetime.fromisocalendar(int(year), int(week), 1).date()
    week_end = datetime.fromisocalendar(int(year), int(week), 7).date()
    week_dates['week'].append(x)
    week_dates['date'].append(week_start)
    week_dates['date.to'].append(week_end)
merged = merged.join(pd.DataFrame(data=week_dates).set_index('week'))

merged = merged.reindex([  # sort
    'date', 'date.to', 'week.confirmed', 'week.investigated', 'week.healthcare', 'week.rhoccupant', 'week.loc.family', 'week.loc.work',
    'week.loc.school', 'week.loc.hospital', 'week.loc.otherhc', 'week.loc.rh', 'week.loc.prison', 'week.loc.transport', 'week.loc.shop',
    'week.loc.restaurant', 'week.loc.sport', 'week.loc.gathering_private', 'week.loc.gathering_organized', 'week.loc.other', 'week.loc.unknown',
    'week.sent_to.quarantine', 'week.src.quarantine', 'week.src.import', 'week.src.import-related', 'week.src.local', 'week.src.unknown',
    'week.from.aus', 'week.from.aut', 'week.from.aze', 'week.from.bel', 'week.from.bgr', 'week.from.bih', 'week.from.cze', 'week.from.mne',
    'week.from.dnk', 'week.from.dom', 'week.from.est', 'week.from.fra', 'week.from.grc', 'week.from.hrv', 'week.from.irn', 'week.from.ita',
    'week.from.kaz', 'week.from.xkx', 'week.from.hun', 'week.from.mkd', 'week.from.mlt', 'week.from.mar', 'week.from.fsm', 'week.from.deu',
    'week.from.pak', 'week.from.pol', 'week.from.rou', 'week.from.rus', 'week.from.svk', 'week.from.srb', 'week.from.esp', 'week.from.swe',
    'week.from.che', 'week.from.tur', 'week.from.ukr', 'week.from.gbr', 'week.from.usa', 'week.from.are'
], axis='columns')

# new NIJZ files report only from week 23 onwards, take preceeding data from archival CSV
df_archive = pd.read_csv(os.path.join(CSV_FOLDER, 'stats-weekly-archive.csv'), index_col='week')
df_archive = df_archive.iloc[:13]  # keep range 2020-10 to 2020-22
merged.drop([f'2020-{x}' for x in range(10, 23)], axis='rows', inplace=True)
merged = pd.concat([df_archive, merged])

filename = os.path.join(CSV_FOLDER, 'stats-weekly.csv')
old_hash = sha1sum(filename)
merged.to_csv(filename, line_terminator='\r\n')

if old_hash != sha1sum(filename):
    with open(f'{filename}.timestamp', 'w', newline='') as f:
        f.write(f'{int(time.time())}\n')
