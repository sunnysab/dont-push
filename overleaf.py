import json
import logging
import time
from dataclasses import dataclass
from typing import override

import requests
from socketIO_client import SocketIO
from lxml import etree


# logging.basicConfig(level=logging.DEBUG)

def _sha1(data: str) -> str:
    import hashlib
    return hashlib.sha1(data.encode()).hexdigest()

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

    @staticmethod
    def on_update_error(details: tuple):
        """ 文档修改失败 """
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

    @staticmethod
    @override
    def on_update_error(details: tuple):
        print('Update error:', details)


class ProjectClient:
    def __init__(self, cookie: dict, project_id: str, callbacks: ProjectCallback = ProjectCallback()):
        self._client = None
        # connection id -> user(userinfo, cursor)
        self.users = {}
        self.callbacks = callbacks
        self.cookie = cookie
        self.project_id = project_id
        self.info_dict = None

        self.current_doc_id: str = ''
        """  当前文档的 id """
        self.current_doc_text: str = ''
        """ 当前文档的全部内容 """
        self.next_version = 0
        """ 当前文档的版本号（从文档创建开始计数） """

    def who(self, connection_id: str) -> str | None:
        """ 根据连接编号获取用户信息 """
        if connection_id in self.users:
            user = self.users[connection_id]
            return f'{user["name"]}({user["email"]})'
        return None

    def root_document(self):
        """ 获取根文档的 id """
        return self.info_dict['project']['rootDoc_id']

    def _on_project_info(self, project: dict):
        """
        event: joinProjectResponse
        :param project:
        :return:
        """
        self.info_dict = project
        self.callbacks.on_project_updated(project)

    def _on_update_user(self, user: dict):
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

    def _on_someone_disconnected(self, connection_id: str):
        """
        event: clientTracking.clientDisconnected
        :param connection_id:
        :return:
        """
        if connection_id in self.users:
            self.users[connection_id]['online'] = False
            self.users[connection_id]['lastSeen'] = time.time()

        self.callbacks.on_disconnected(connection_id)

    def _on_change(self, change: dict):
        """
        event: otUpdateApplied
        :param {"doc":"65f9462e5845636c9a353faf",
                "op":[{"p":1189,"i":"g"},{"p":1189,"d":"g"}],
                "v":81,
                "meta":{"source":"P.mjeGUE16Cydbd67ZBB5u","user_id":"644bc9e06ad7d9204f9c8948","ts":1728792367895},
                "lastV":80,
                "hash":"9f8e1663d2eb9a2e6a19a7484fa57863b0ffcd4e"}
                对于当前客户端的修改，返回另一种形式：
                [{"v":83,"doc":"65f9462e5845636c9a353faf"}]
                其中，v 表示当前文档的版本号
        :return:
        """
        self.next_version = change['v']
        self.callbacks.on_change(change)

    def _on_update_error(self, *details):
        """
        event: otUpdateError
        :param "Invalid hash", {
                    "project_id":"65f9462e5845636c9a353fa6",
                    "doc_id":"65f9462e5845636c9a353faf",
                    "error":"Invalid hash",
                    "_id":"doc:document-updater-prod-66fb5d46b9-sl5lr:16ef6681-8278191"}
        :return:
        """
        logging.error('Error: %s', details)
        self.callbacks.on_update_error(details)

    def _do_op(self, method, content, position):
        """ 在文档上执行修改 """
        match method:
            case 'd':
                self.current_doc_text = self.current_doc_text[:position] + self.current_doc_text[position + len(content):]
            case 'i':
                self.current_doc_text = self.current_doc_text[:position] + content + self.current_doc_text[position:]
            case _:
                raise ValueError('method must be "d" or "i"')

    def edit_many(self, changes: list[tuple[str, str, int]]):
        """
        批量修改文档
        :param changes: [(method, content, position), ...]
        :return:
        """
        for method, content, position in changes:
            assert method in ['d', 'i'], 'method must be "d" or "i"'
            assert position >= 0, 'position must be greater than or equal to 0'
            assert content, 'content must not be empty'
            self._do_op(method, content, position)

        # ["65f9462e5845636c9a353faf",{"doc":"65f9462e5845636c9a353faf","op":[{"p":0,"d":"d"}],"v":83,"lastV":82,"hash":"9f8e1663d2eb9a2e6a19a7484fa57863b0ffcd4e"}]
        operations = [{'p': position, method: content} for method, content, position in changes]
        # 在 DevTools 中搜索 "applyOtUpdate", 然后下断点。
        # 触发断点后根据调用栈找到调用位置
        self._client.emit('applyOtUpdate', self.current_doc_id, {
            "doc": self.current_doc_id,
            "op": operations,
            "v": self.next_version,
            "lastV": self.next_version - 1,
            "hash": _sha1(f'blob {len(self.current_doc_text)}\x00{self.current_doc_text}')
        }, callback=lambda *data: None)

    def edit(self, method: str, content: str, position: int):
        """
        event: applyOtUpdate
        :param method:
        :param content:
        :param position:
        :return:
        """
        return self.edit_many([(method, content, position)])

    def set_position(self, pos: tuple[int, int] = None):
        """ 设置当前用户的光标位置 """
        if pos:
            row, col = pos
            self._client.emit('clientTracking.updatePosition', {
                'row': row,
                'column': col,
                'doc_id': self.root_document()
            })
        else:
            self._client.emit('clientTracking.updatePosition', {
                'doc_id': None
            })

    def request_connected_users(self):
        """ 发送“获取当前连接的用户”请求 """
        def set_connected_clients(data):
            _unknown, data = data
            for user in data:
                # getConnectedClients 请求到的用户结构体和 clientUpdated 事件的用户结构体略有差别
                user['id'] = user['client_id']
                self._on_update_user(user)

        self._client.emit('clientTracking.getConnectedUsers', callback=lambda *data: set_connected_clients(data))

    def join_document(self, document_id: str):
        """ 注册当前客户端，否则收不到文档修改消息 """
        if self.current_doc_id:
            self.leave_document(self.current_doc_id)

        def update_document(data: tuple):
            _unknown, lines, version, _unknown2, _unknown3 = data
            self.current_doc_text = '\n'.join(lines)
            self.next_version = version

        self._client.emit('joinDoc', document_id, {"encodeRanges": True}, callback=lambda *data: update_document(data))
        self.current_doc_id = document_id

    def leave_document(self, document_id: str):
        """ 离开文档 """
        def leave_callback(data):
            pass

        self._client.emit('leaveDoc', document_id, callback=leave_callback)
        self.current_doc_id = ''

    def _register(self):
        count = 3
        while self.info_dict is None and count:
            self._client.wait(1)
            count -= 1

        root_doc_id = self.root_document()

        self.set_position(None)
        self.request_connected_users()
        self.join_document(root_doc_id)
        self.set_position((0, 0))

    def run(self):
        cookie_str = '; '.join([f'{key}={value}' for key, value in self.cookie.items()])
        self._client = SocketIO('https://www.overleaf.com',
                                params={
                                    't': int(time.time()),
                                    'projectId': project_id
                                },
                                headers={'Cookie': cookie_str})

        self._client.on('joinProjectResponse', lambda data: self._on_project_info(data))
        self._client.on('clientTracking.clientUpdated', lambda data: self._on_update_user(data))
        self._client.on('clientTracking.clientDisconnected', lambda data: self._on_someone_disconnected(data))
        self._client.on('otUpdateApplied', lambda data: self._on_change(data))
        self._client.on('otUpdateError', lambda *data: self._on_update_error(data))
        self._register()

    def wait(self, duration: int = 2 ** 32):
        assert duration >= 1, 'duration must be greater than 1'

        start_sec = time.time()
        while True:
            self._client.wait(0.5)
            elapsed = time.time() - start_sec

            if elapsed >= duration:
                break

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

    ws.wait(3)
    ws.edit('i', 'Hello, world!', 0)
    ws.wait()
