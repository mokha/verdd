# -*- coding: utf-8 -*-
import requests
from django.conf import settings
import urllib.parse


class SemanticAPI:
    def __init__(self, username="", password=""):
        self.wiki_url = settings.WIKI_URL
        self.api_url = self.wiki_url.rstrip("/") + "/api.php"
        self.session = requests.Session()
        if username and password:
            self.username = username
            self.password = password
            self._login()

    def _login(self):
        # get login token
        r1 = self.session.get(
            self.api_url,
            params={
                "format": "json",
                "action": "query",
                "meta": "tokens",
                "type": "login",
            },
        )
        r1.raise_for_status()  # login failed

        # log in
        r2 = self.session.post(
            self.api_url,
            data={
                "format": "json",
                "action": "login",
                "lgname": self.username,
                "lgpassword": self.password,
                "lgtoken": r1.json()["query"]["tokens"]["logintoken"],
            },
        )
        if r2.json()["login"]["result"] != "Success":
            raise RuntimeError(r2.json()["login"]["reason"])

        # get edit token
        r3 = self.session.get(
            self.api_url,
            params={
                "format": "json",
                "action": "query",
                "meta": "tokens",
            },
        )
        self.token = r3.json()["query"]["tokens"]["csrftoken"]

    def get(self, param):
        param.update({"format": "json"})
        return self.session.get(self.api_url, params=param).json()

    def ask(self, query=()):
        """
        query=[[Lang::Fin]]%0D[[POS::N]]|%3FPOS|sort=POS|order=desc
        :return:
        """
        q = "|".join(query)

        param = {"query": q, "action": "ask"}

        return self.get(param)

    def parse(self, title):
        """

        :param title: The page title
        :return:
        """
        param = {"action": "parse", "page": title}
        return self.get(param)

    def post(self, data):
        data.update(
            {
                "format": "json",
                "token": self.token,
            }
        )
        return self.session.post(self.api_url, data=data)


if __name__ == "__main__":
    sa = SemanticAPI()
    r = sa.ask(
        query=(
            "[[Lang::Fin]]\n[[POS::N]]\n[[Fin:suomi]]",
            "?Category",
            "?POS",
            "sort=POS",
            "order=desc",
        )
    )
