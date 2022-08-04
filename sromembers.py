from xmlrpc.client import boolean
from bs4 import BeautifulSoup as bs
from urllib.request import urlopen
import ssl
from sro_dict import SRO_DICT

SRO_DICT = SRO_DICT

DATA = []


def get_html(url):
    context = ssl._create_unverified_context()
    res = urlopen(url, context=context)
    return res

def get_page_data(html):
    soup = bs(html, 'lxml')
    trs = soup.find('table', attrs={'class':'table'}).find('tbody').find_all('tr')
    for tr in trs:
        tds = tr.find_all('td')
        comp_fund_odo_sum = ''.join(tds[6].text.split())
        if comp_fund_odo_sum == '':
            DATA.append('0')
        else:
            DATA.append(comp_fund_odo_sum)

def is_link_on_page(html):
    soup = bs(html, 'lxml')
    tr = soup.find('table', attrs={'class':'table'}).find('tbody').find('tr', attrs={'class':'sro-link'})
    return boolean(tr)

def get_fond_amount(url):
    page_number=1

    while is_link_on_page(get_html(str(url)+str(page_number))):
        get_page_data(get_html(url+str(page_number)))
        print('Information from page ' + str(page_number) + ' collected')
        page_number += 1
        print('Going to page ' + str(page_number))

    return(sum(int(i) for i in DATA))

for val in SRO_DICT.values():
    url = ('https://reestr.nostroy.ru/reestr/clients/'
        + str(val)
        +'/members?m_fulldescription=&m_shortdescription=&bms_id=1&m_'
        +'ogrnip=&m_inn=&m_compensationfundfee_vv=&m_compensationfundfee_odo=&bmt_id=&u_registrationnumber=&sort=m.id&direction=desc&page='
    )
    
    def get_info_per_sro():
        fond_amount = get_fond_amount(url)
        sro_name = list(SRO_DICT.keys())[list(SRO_DICT.values()).index(val)]
        return {sro_name:fond_amount}
    
    DATA = []
    
    OUTPUT_DATA = []
    
    OUTPUT_DATA.append(get_info_per_sro())
    with open(r"/home/alex/Work/sroinfo.txt", "a") as file:
        for item in OUTPUT_DATA:
            for key, value in item.items():
                file.write(key + ' : ' + str(value) + '\n')

print('Writing to file complete successfuly')

