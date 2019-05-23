import requests
import json
from django.conf import settings


class WikiTool:
    '''
    Implemented by Mika Hämäläinen
    '''

    def __init__(self, username, password, language):
        self.wiki_url = settings.WIKI_PATH
        self.username = username
        self.password = password
        self.login_cookies = {}
        self.token = ""
        self.cookies = {}
        self.language = language

    def post(self, url, data):
        r = requests.post(url, data=data, cookies=self.cookies)
        success = r.status_code >= 200 and r.status_code < 300
        if "mediawiki-api-error" in dict(r.headers).keys():
            success = False
        if success:
            try:
                d = r.json()
            except:
                d = r.text + json.dumps(dict(r.headers))
        else:
            d = r.text + json.dumps(dict(r.headers))
        return success, d, r.cookies

    def login(self):
        data = {"action": "login", "lgname": self.username, "lgpassword": self.password, "format": "json"}
        success, loginResults, c = self.post(self.wiki_url + "api.php", data)
        self.cookies = c
        if not success:
            return False
        if loginResults["login"]["result"] == "NeedToken":
            confirmationData = {"action": "login", "lgname": self.username, "lgpassword": self.password,
                                "lgtoken": loginResults["login"]["token"], "format": "json"}
            success, loginResults, c = self.post(self.wiki_url + "api.php", confirmationData)
            if not success:
                return False
        self.cookies = c
        return True

    def get_token(self):
        data = {"action": "query", "meta": "tokens", "format": "json"}
        success, loginResults, c = self.post(self.wiki_url + "api.php", data)
        if not success:
            return False
        self.token = loginResults["query"]["tokens"]["csrftoken"]
        self.cookies = c
        return True

    def get_pages(self, additional_parameters="", all_pages=False):
        post_parameters = {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + self.language.title(),
                           "cmlimit": 100000, "format": "json", "token": self.token}
        if all_pages:
            post_parameters["list"] = "allpages"
            del post_parameters["cmtitle"]

        post_parameters.update(additional_parameters)
        success, results, c = self.post(self.wiki_url + "api.php", post_parameters)
        return success, results

    def get_a_page(self, id, by_parameter="pageids"):
        postParameters = {"action": "query", by_parameter: id, "export": True, "format": "json"}
        success, results, c = self.post(self.wiki_url + "api.php", postParameters)
        return success, results
