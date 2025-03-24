import pyqtgraph as pg
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph import QtCore

class ProcessParams(ParameterTree):
    def __init__(self):
        super().__init__()

        self.params = [
            {'name':'Segment 1','type':'group','expanded':False,'children':[
                {'name':'Time','type':'int', 'value':'20'},
                {'name':'Temperature','type':'int','value':'300'},
                {'name':'Ar Flow','type':'int','value':'75'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 2','type':'group','expanded':False,'children':[
                {'name':'Time','type':'int', 'value':'20'},
                {'name':'Temperature','type':'int','value':'300'},
                {'name':'Ar Flow','type':'int','value':'75'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 3','type':'group','expanded':False,'children':[
                {'name':'Time','type':'int', 'value':'20'},
                {'name':'Temperature','type':'int','value':'300'},
                {'name':'Ar Flow','type':'int','value':'75'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 4','type':'group','expanded':False,'children':[
                {'name':'Time','type':'int', 'value':'20'},
                {'name':'Temperature','type':'int','value':'300'},
                {'name':'Ar Flow','type':'int','value':'75'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 5','type':'group','expanded':False,'children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 6','type':'group','expanded':False,'children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 7','type':'group','expanded':False,'children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 8','type':'group','expanded':False,'children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'}
            ]},
            {'name':'Segment 9','type':'group','expanded':False,'children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 10','type':'group','expanded':False,'children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]}
        ]

        self.p = Parameter.create(name='self.params',type='group',children=self.params)
        self.setParameters(self.p,showTop=False)

    def getValue(self,segment:int, child):
        return self.p.param(f'Segment {segment}',child).value()

class OtherParams(ParameterTree):
    
    log_interval_change = QtCore.pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.running_explode = False
        self.params = [
            {'name':'Logging Interval (s)','type':'int','value':30},
            {'name':'Overpressure Limit (Torr)','type':'int','value':800},
            {'name':'Fill Parameters','type':'group','children':[
                {'name':'Approach Pressure (Torr)','type':'int','value':745},
                {'name':'Fill Pressure (Torr)','type':'int','value':750},
                {'name':'Approach Ar Flow (sccm)','type':'int','value':'100'},
                {'name':'Fill Ar Flow (sccm)','type':'int','value':'1000'}
            ]}
        ]
        self.p = Parameter.create(name='self.params',type='group',children=self.params)
        self.setParameters(self.p,showTop=False)

        self.p.child('Logging Interval (s)').sigValueChanged.connect(self.emitChange)
        self.p.child('Fill Parameters','Fill Pressure (Torr)').sigValueChanged.connect(self.forceApproachPressure)

    def emitChange(self):
        self.log_interval_change.emit(self.getValue('Logging Interval (s)'))

    def getValue(self,child):
        return self.p.param(child).value()
    def getFillValue(self,child):
        return self.p.param('Fill Parameters',child).value()

    def forceApproachPressure(self):
        ## forces approach press =< fill pressure
        newPressure = self.getFillValue('Fill Pressure (Torr)')
        if  newPressure < self.getFillValue('Approach Pressure (Torr)'):
            # print(oldPressure)           
            self.p.param('Fill Parameters','Approach Pressure (Torr)').setValue(int(newPressure-5))