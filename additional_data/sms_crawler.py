import requests
from bs4 import BeautifulSoup
from mikatools import *
import pprint
url = "https://satni.uit.no/termwiki/index.php?title=Kategoriija:Nu%C3%B5rtts%C3%A4%C3%A4%CA%B9m_n%C3%B5%C3%B5mt%C3%B5%C3%B5zz"

def get_urls():
	urls = []
	r = requests.get(url)
	soup = BeautifulSoup(r.text, 'html.parser')
	pages = soup.find("div", id="mw-pages")
	links = pages.find_all("a")
	base = "https://" + url.split("://")[1].split("/")[0]
	for link in links:
		href = link['href']
		urls.append(base + href)
	return urls

def parse_table(table):
	data = []

	rows = table.find_all('tr')
	for row in rows:
		cols = row.find_all('td')
		cols = [ele for ele in cols]
		data.append([ele for ele in cols if ele])
	return data

def get_words():
	urls = get_urls()
	words = []
	for url in urls:
		print(url)
		r = requests.get(url)
		soup = BeautifulSoup(r.text, 'html.parser')
		pages = soup.find("div", id="bodyContent")
		tables =  pages.find_all("table" , { "class" : "wikitable"})
		for table in tables:
			table = parse_table(table)
			word_data = {"sms":[], "fin":[]}
			save_word = False
			for row in table:
				if len(row) == 0:
					continue
				elif "Nuõrttsää’mǩiõll" in row[0].text:
					save_word = True
					lis = row[2].find_all('li')
					for li in lis:
						lemma = li.find("a").text
						if "Sanctioned: true" in li.text:
							s = True
						else:
							s = False
						word_data["sms"].append({"word": lemma, "sanctioned": s, "url" : url})
				elif "Suomen kieli" in row[0].text:
					lis = row[2].find_all('li')
					for li in lis:
						lemma = li.find("a").text
						if "Sanctioned: true" in li.text:
							s = True
						else:
							s = False
						word_data["fin"].append({"word": lemma, "sanctioned": s, "url" : url})
			if save_word:
				words.append(word_data)
	json_dump(words, "sms_termwiki.json")

get_words()
