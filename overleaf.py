import json
import logging
import time
from dataclasses import dataclass
from typing import override

import requests
from socketIO_client import SocketIO
from lxml import etree


# logging.basicConfig(level=logging.DEBUG)

@dataclass
class ProjectCallback:
    @staticmethod
    def on_project_updated(project: dict):
        """" 服务端推送文档基本信息 """
        pass

    @staticmethod
    def on_user_updated(user: dict):
        """ 用户位置更新/上线消息 """
        pass

    @staticmethod
    def on_disconnected(connection_id: str):
        """ 用户下线消息 """
        pass

    @staticmethod
    def on_change(change: dict):
        """ 文档修改消息 """
        pass


class ProjectLogger(ProjectCallback):
    @staticmethod
    @override
    def on_project_updated(project: dict):
        print('Project updated:', project)

    @staticmethod
    @override
    def on_user_updated(user: dict):
        print('User updated:', user)

    @staticmethod
    @override
    def on_disconnected(connection_id: str):
        print('User disconnected:', connection_id)

    @staticmethod
    @override
    def on_change(change: dict):
        print('Change:', change)


class ProjectClient:
    def __init__(self, cookie: dict, project_id: str, callbacks: ProjectCallback = ProjectCallback()):
        self._client = None
        self.cookie = cookie
        self.project_id = project_id
        self.info_dict = None
        # connection id -> user(userinfo, cursor)
        self.users = {}
        self.callbacks = callbacks

    def who(self, connection_id: str) -> str | None:
        """ 根据连接编号获取用户信息 """
        if connection_id in self.users:
            user = self.users[connection_id]
            return f'{user["name"]}({user["email"]})'
        return None

    def _update_project(self, project: dict):
        """
        event: joinProjectResponse
        :param project:
        :return:
        """
        self.info_dict = project
        self.callbacks.on_project_updated(project)

    def _update_users(self, user: dict):
        """
        event: clientTracking.clientUpdated
        :param {"row":19,
                "column":14,
                "doc_id":"65f9462e5845636c9a353faf",
                "id":"P.r5rP7AC1YT5Fo0T2BBRK",
                "user_id":"5eb3865a68a19f0001d912d9",
                "email":"i@sunnysab.cn",
                "name":"sunnysab"
               }
        """
        key = user['id']
        user['online'] = True
        user['lastSeen'] = time.time()
        if key not in self.users:
            self.users[key] = user
        else:
            self.users[key].update(user)

        self.callbacks.on_user_updated(user)

    def _disconnected(self, connection_id: str):
        """
        event: clientTracking.clientDisconnected
        :param connection_id:
        :return:
        """
        if connection_id in self.users:
            self.users[connection_id]['online'] = False
            self.users[connection_id]['lastSeen'] = time.time()

        self.callbacks.on_disconnected(connection_id)

    def _change(self, change: dict):
        """
        event: otUpdateApplied
        :param {"doc":"65f9462e5845636c9a353faf",
                "op":[{"p":1189,"i":"g"},{"p":1189,"d":"g"}],
                "v":81,
                "meta":{"source":"P.mjeGUE16Cydbd67ZBB5u","user_id":"644bc9e06ad7d9204f9c8948","ts":1728792367895},
                "lastV":80,
                "hash":"9f8e1663d2eb9a2e6a19a7484fa57863b0ffcd4e"}
        :return:
        """
        self.callbacks.on_change(change)

    def run(self):
        cookie_str = '; '.join([f'{key}={value}' for key, value in self.cookie.items()])
        self._client = SocketIO('https://www.overleaf.com',
                                params={
                                    't': int(time.time()),
                                    'projectId': project_id
                                },
                                headers={'Cookie': cookie_str})

        self._client.on('joinProjectResponse', lambda data: self._update_project(data))
        self._client.on('clientTracking.clientUpdated', lambda data: self._update_users(data))
        self._client.on('clientTracking.clientDisconnected', lambda data: self._disconnected(data))
        self._client.on('otUpdateApplied', lambda data: self._change(data))
        self._client.wait_for_callbacks()

    def wait(self):
        while True:
            self._client.wait(1)

class Client:
    _BASE_URL = 'https://www.overleaf.com'

    def __init__(self, cookie_session: dict):
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
        response = self.http_client.get(URL, cookies=self.cookie_session)
        response.raise_for_status()

        page = etree.HTML(response.text)
        projects_element = page.xpath('//meta[@name="ol-prefetchedProjectsBlob"]')[0]
        projects_json = projects_element.get('content')
        projects = json.loads(projects_json)
        return projects['projects']

    def open(self, project_id: str, callbacks: ProjectCallback) -> ProjectClient:
        """ 打开一个项目的 websocket 连接. """
        ws_client = ProjectClient(self.cookie_session, project_id, callbacks)
        ws_client.run()
        return ws_client

if __name__ == '__main__':
    from cookie import load_browser_cookie
    cookie_dict = load_browser_cookie('firefox')

    client = Client(cookie_dict)

    projects = client.get_projects()
    print(projects)

    # 选择一个项目，打开它的 websocket
    # project_id = projects[0]['id']
    project_id = '65f9462e5845636c9a353fa6'

    callbacks = ProjectLogger()
    ws = client.open(project_id, callbacks=callbacks)

    ws.wait()