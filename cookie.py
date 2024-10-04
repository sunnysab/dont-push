from http.cookiejar import CookieJar


def load_browser_cookie(browser: str) -> CookieJar:
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
    return cookies
