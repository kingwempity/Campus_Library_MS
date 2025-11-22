try:
    import pymysql  # 纯 Python 驱动，Windows 上更易安装
    pymysql.install_as_MySQLdb()
except Exception:
    # 未安装时忽略，启动前按文档安装依赖即可
    pass

