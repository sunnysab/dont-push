import json
import logging
import time
import requests
from socketIO_client import SocketIO
from lxml import etree


# logging.basicConfig(level=logging.DEBUG)

class ProjectClient:
    def __init__(self, cookie: str, project_id: str):
        self._client = None
        self.cookie = cookie
        self.project_id = project_id
        self.info_dict = None

    def run(self):
        self._client = SocketIO('https://www.overleaf.com',
                                params={
                                    't': int(time.time()),
                                    'projectId': project_id
                                },
                                headers={'Cookie': self.cookie})

        def set_project_infos(project_infos_dict):
            self.info_dict = project_infos_dict.get("project", {})
        self._client.on('joinProjectResponse', set_project_infos)

class Client:
    _BASE_URL = 'https://www.overleaf.com'

    def __init__(self, cookie_session: str):
        self.cookie_session = cookie_session
        self.http_client = requests.Session()

    def get_projects(self) -> list[dict]:
        """ 获取用户的项目（文档）列表
        :return: 单个 Project 示例：

        {'id': '65f9462e5845636c9a353fa6',
         'name': '测试',
         'lastUpdated': '2024-10-04T07:47:11.884Z',
         'lastUpdatedBy': {'id': '5eb3865a68a19f0001d912d9', 'email': 'i@sunnysab.cn', 'firstName': 'sunnysab', 'lastName': ''},
         'accessLevel': 'owner',
         'source': 'owner',
         'archived': False,
         'trashed': False,
         'owner': {'id': '5eb3865a68a19f0001d912d9', 'email': 'i@sunnysab.cn', 'firstName': 'sunnysab', 'lastName': ''}
        }
        """
        URL = 'https://www.overleaf.com/project'
        response = self.http_client.get(URL, cookies={'overleaf_session2': self.cookie_session})
        response.raise_for_status()

        page = etree.HTML(response.text)
        projects_element = page.xpath('//meta[@name="ol-prefetchedProjectsBlob"]')[0]
        projects_json = projects_element.get('content')
        projects = json.loads(projects_json)
        return projects['projects']

    def open(self, project_id: str) -> ProjectClient:
        """ 打开一个项目的 websocket 连接. """
        # wss://www.overleaf.com/socket.io/1/websocket/jNwcOnDPJ_p4YNmphQ_P?projectId=65f9462e5845636c9a353fa6
        ws_client = ProjectClient(self.cookie_session, project_id)
        ws_client.run()
        return ws_client

if __name__ == '__main__':
    # from cookie import load_browser_cookie
    # cookie_string = load_browser_cookie('firefox')

    cookie_string = 's%3A6fHFW0DrUU3x_h8F1VWO_jDlYk8AwsPw.EW4snnZyY8sOwi6jtyfmZH4%2FTnA%2B3aS3J4fJExKfHSU'
    client = Client(cookie_string)

    projects = client.get_projects()
    print(projects)

    # 选择一个项目，打开它的 websocket
    # project_id = projects[0]['id']
    project_id = '65f9462e5845636c9a353fa6'
    client.open(project_id)