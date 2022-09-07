import requests
import sro_dict
from sys import argv

def get_compfund_see_odo_sum_from_page(url, page_num):
    r = requests.post(url, json={"filters": {"member_status": 1}, "page": page_num, "pageCount": "100", "sortBy": {}})
    data_dict = r.json()
    data = data_dict['data']['data']
    compensation_fund_fee_odo_per_page = 0
    for i in data:
        try:
            compensation_fund_fee_odo_per_page = int(i['compensation_fund_fee_odo']) + compensation_fund_fee_odo_per_page
        except:
            pass
    return compensation_fund_fee_odo_per_page

def get_number_of_pages(url):
    r = requests.post(url, json={"filters": {"member_status": 1}, "page": 1, "pageCount": "100", "sortBy": {}})
    data_dict = r.json()
    number_of_pages = int(data_dict['data']['countPages'])
    return number_of_pages

def get_compfund_see_odo_sum_per_sro(url):
    comfund_odo_total = 0
    for page in range(1, get_number_of_pages(url)+1):
        comfund_odo_total = comfund_odo_total + get_compfund_see_odo_sum_from_page(url, page)
    return comfund_odo_total

def write_to_file(filename, data):
    with open(filename, "a") as file:
        file.write(data)

def main():
    script, sro = argv
    
    if sro == 'nostroy':
        filename = "/home/alex/Work/nostroy.txt"
        for key, value in sro_dict.NOSTROY_SRO_DICT.items():
            url = 'https://api-open-nostroy.anonamis.ru/api/sro/' + str(value) +'/member/list'
            data = key + " : " + str(get_compfund_see_odo_sum_per_sro(url)) + "\n"
            write_to_file(filename, data)
            print("Info added to file")
        print("Script comleted with status: Done")
    elif sro == 'nopriz':
        filename = "/home/alex/Work/nopriz.txt"
        for key, value in sro_dict.NOPRIZ_SRO_DICT.items():
            url = 'https://reestr.nopriz.ru/api/sro/' + str(value) +'/member/list'
            data = key + " : " + str(get_compfund_see_odo_sum_per_sro(url)) + "\n"
            write_to_file(filename, data)
            print("Info added to file")
        print("Script comleted with status: Done")
    else:
        print('Unknown argument: '+ sro + '. Please type "nopriz" or "nostroy"')
    
if __name__ == '__main__':
    main()