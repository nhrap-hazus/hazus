import os

def femaSetProxies():
    """Sets environmental proxies for a FEMA PC to access web services behind the firewall
    """
    os.environ["HTTP_PROXY"] = 'http://proxy.apps.dhs.gov:80'
    os.environ["HTTPS_PROXY"] = 'http://proxy.apps.dhs.gov:80'