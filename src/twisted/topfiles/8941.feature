twisted.internet.reactor.spawnProcess now does not raise a deprecation warning on Unicode arguments. It will encode Unicode arguments down to bytes using the filesystem encoding on UNIX and Python 2 on Windows, and pass Unicode through unchanged on Python 3 on Windows.
