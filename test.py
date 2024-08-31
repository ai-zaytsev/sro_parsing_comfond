import requests

def fetch(url, json_data=None):
    response = requests.post(url, json=json_data, verify=False)
    return response.json()

def get_nostroy_dict_items():
    nostroy_sro_dict = {}
    for i in range(90, 101):
        sro_url = f"https://reestr.nostroy.ru/api/sro/{i}"
        try:
            data_dict = fetch(sro_url)
            short_description = data_dict['data']['short_description']
            registration_number = data_dict['data']['registration_number']
            dict_key = f"{registration_number} {short_description}"
            nostroy_sro_dict[dict_key] = i
            print(f"Added {short_description} with ID {i}")
        except Exception as e:
            print(f"{i} not found: {e}")
    return nostroy_sro_dict

if __name__ == "__main__":
    nostroy_dict = get_nostroy_dict_items()
    print(nostroy_dict)