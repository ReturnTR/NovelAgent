#!/usr/bin/env python3
import getpass
import mysql.connector
from mysql.connector import Error
import argparse

def execute_remote_mysql_command(host, user, password, database, port, sql_command):
    """
    执行远程MySQL命令
    
    Args:
        host: MySQL服务器主机名或IP地址
        user: 数据库用户名
        password: 数据库密码
        database: 要使用的数据库名称
        port: MySQL服务器端口
        sql_command: 要执行的SQL命令
    
    Returns:
        执行结果
    """
    connection = None
    cursor = None
    result = None
    
    try:
        # 连接到MySQL服务器
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port
        )
        
        if connection.is_connected():
            print(f"成功连接到MySQL服务器: {host}:{port}")
            
            # 创建游标对象，使用buffered=True避免Unread result错误
            cursor = connection.cursor(buffered=True)
            
            # 执行SQL命令
            cursor.execute(sql_command)
            
            # 检查是否有结果集
            if cursor.with_rows:
                # 获取结果
                result = cursor.fetchall()
            else:
                # 对于没有结果集的语句，提交事务
                connection.commit()
                print(f"命令执行成功，影响行数: {cursor.rowcount}")
                
    except Error as e:
        print(f"错误: {e}")
    finally:
        # 关闭游标和连接
        if cursor:
            try:
                cursor.close()
            except Error as e:
                print(f"关闭游标时错误: {e}")
        if connection and connection.is_connected():
            connection.close()
            print("数据库连接已关闭")
    
    return result

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='执行远程MySQL命令')
    parser.add_argument('sql_command', help='要执行的SQL命令')
    args = parser.parse_args()
    
    # 配置信息
    host = '192.168.31.5'
    # host = '127.0.0.1'
    user = 'root'
    port = 3306
    # 交互式输入密码
    password = "caonima990316"

    # 交互式输入数据库名称
    database = "NovelWorld"
    
    # 从命令行参数获取SQL命令
    sql_command = args.sql_command
    
    # 执行MySQL命令
    result = execute_remote_mysql_command(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        sql_command=sql_command
    )

    print(result)

if __name__ == "__main__":
    main()
