import os
import pandas as pd
import pyodbc as py

def getStudyRegions():
    """Gets all study region names imported into your local Hazus install

    Returns:
        studyRegions: list -- study region names
    """
    comp_name = os.environ['COMPUTERNAME']
    conn = py.connect('Driver=ODBC Driver 11 for SQL Server;SERVER=' +
        comp_name + '\HAZUSPLUSSRVR; UID=SA;PWD=Gohazusplus_02')
    exclusionRows = ['master', 'tempdb', 'model', 'msdb', 'syHazus', 'CDMS', 'flTmpDB']
    cursor = conn.cursor()
    cursor.execute('SELECT [StateID] FROM [syHazus].[dbo].[syState]')   
    for state in cursor:
        exclusionRows.append(state[0])
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sys.databases')
    studyRegions = []
    for row in cursor:
        if row[0] not in exclusionRows:
            studyRegions.append(row[0])
    studyRegions.sort(key=lambda x: x.lower())
    return studyRegions

class HazusDB():
    """Creates a connection to the Hazus SQL Server database with methods to access
    databases, tables, and study regions
    """
    def __init__(self):
        self.conn = self.createConnection()
        self.cursor = self.conn.cursor()
        self.databases = self.getDatabases()
    
    def createConnection(self):
        comp_name = os.environ['COMPUTERNAME']
        conn = py.connect('Driver=ODBC Driver 11 for SQL Server;SERVER=' +
            comp_name + '\HAZUSPLUSSRVR; UID=SA;PWD=Gohazusplus_02')
        self.conn = conn
        return conn
    
    def getDatabases(self):
        query = 'SELECT name FROM sys.databases'
        df = pd.read_sql(query, self.conn)
        return df
    
    def getTables(self, databaseName):
        query = 'SELECT * FROM [%s].INFORMATION_SCHEMA.TABLES;' % databaseName
        df = pd.read_sql(query, self.conn)
        self.tables = df
        return df

    def getStudyRegions(self):
        exclusionRows = ['master', 'tempdb', 'model', 'msdb', 'syHazus', 'CDMS', 'flTmpDB']
        self.cursor.execute('SELECT [StateID] FROM [syHazus].[dbo].[syState]')   
        for state in self.cursor:
            exclusionRows.append(state[0])
        query = 'SELECT * FROM sys.databases'
        df = pd.read_sql(query, self.conn)
        studyRegions = df[~df['name'].isin(exclusionRows)]['name']
        studyRegions = studyRegions.reset_index()
        studyRegions = studyRegions.drop('index', axis=1)
        self.studyRegions = studyRegions
        return studyRegions

    def query(self, sql):
        df = pd.read_sql(sql, self.conn)
        return df

    def getHazardBoundary(self, databaseName):
        query = 'SELECT Shape.STAsText() as geom from [%s].[dbo].[hzboundary]' % databaseName
        df = pd.read_sql(query, self.conn)
        return df
        