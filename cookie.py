from http.cookiejar import CookieJar, Cookie


def load_browser_cookie(browser: str) -> str:
    """
    从指定的浏览器中加载 overleaf 站点的 cookie
    """

    import browser_cookie3 as cookie_jar

    load = None
    match browser:
        case "chrome":
            load = cookie_jar.chrome
        case "firefox":
            load = cookie_jar.firefox
        case "edge":
            load = cookie_jar.edge
        case _:
            raise ValueError(f"Browser {browser} not supported")

    cookies: CookieJar = load(domain_name='.overleaf.com')
    try:
        overleaf_session: Cookie = cookies.__dict__['_cookies']['.overleaf.com']['/']['overleaf_session2']
    except ValueError as e:
        raise ValueError("Cookie not found") from e

    return overleaf_session.value


def load_browser_cookie_or_none(browser: str) -> str | None:
    """
    从指定的浏览器中加载 overleaf 站点的 cookie
    """

    try:
        return load_browser_cookie(browser)
    except Exception as _:
        pass
    return None
