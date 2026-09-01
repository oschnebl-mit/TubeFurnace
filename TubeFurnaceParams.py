import pyqtgraph as pg
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph import QtCore

MAX_SEGMENTS = 16 ## FurnaceControl.programFurnace rejects more than this
ALL_GAS_IDS = ['N2','Ar','O2','FG','H2S','H2Se'] ## must match MFCControl.gas_ids keys

class ProcessParams(ParameterTree):
    def __init__(self,n_segments=3,gases=('Ar','H2S')):
        super().__init__()

        self.gas_list = list(gases)
        self.params = [self._make_segment(i) for i in range(1,n_segments+1)]

        self.p = Parameter.create(name='self.params',type='group',children=self.params)
        self.setParameters(self.p,showTop=False)

    def _make_segment(self,segment_number,time=20,temperature=300):
        children = [
            {'name':'Time','type':'int','value':time},
            {'name':'Temperature','type':'int','value':temperature},
        ]
        for gas in self.gas_list:
            children.append({'name':f'{gas} Flow','type':'int','value':0})
        children.append({'name':'Wait for','type':'list','limits':['Time','Temp']})
        return {'name':f'Segment {segment_number}','type':'group','expanded':False,'children':children}

    def getValue(self,segment:int, child):
        return self.p.param(f'Segment {segment}',child).value()

    def addSegment(self):
        n_segments = len(self.p.children())
        if n_segments >= MAX_SEGMENTS:
            return False
        self.p.addChild(self._make_segment(n_segments+1))
        return True

    def addGas(self,gas_name):
        if gas_name not in ALL_GAS_IDS or gas_name in self.gas_list:
            return False
        self.gas_list.append(gas_name)
        for segment in self.p.children():
            segment.insertChild(len(segment.children())-1,{'name':f'{gas_name} Flow','type':'int','value':0}) ## before 'Wait for'
        return True

class OtherParams(ParameterTree):
    
    log_interval_change = QtCore.pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.running_explode = False
        self.params = [
            {'name':'Logging Interval (s)','type':'int','value':30},
            {'name':'Overpressure Limit (Torr)','type':'int','value':800},
            {'name':'Control Zone','type':'list','limits':['1','2','3'],'value':'2'},
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
