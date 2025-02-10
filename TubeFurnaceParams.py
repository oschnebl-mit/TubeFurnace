import pyqtgraph as pg
from pyqtgraph.parametertree import Parameter, ParameterTree

class TubeFurnaceParams(ParameterTree):
    def __init__(self):
        super().__init__()

        self.params = [
            {'name':'Segment 1','type':'group','children':[
                {'name':'Time','type':'int', 'value':'20'},
                {'name':'Temperature','type':'int','value':'300'},
                {'name':'Ar Flow','type':'int','value':'75'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 2','type':'group','children':[
                {'name':'Time','type':'int', 'value':'20'},
                {'name':'Temperature','type':'int','value':'300'},
                {'name':'Ar Flow','type':'int','value':'75'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 3','type':'group','children':[
                {'name':'Time','type':'int', 'value':'20'},
                {'name':'Temperature','type':'int','value':'300'},
                {'name':'Ar Flow','type':'int','value':'75'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 4','type':'group','children':[
                {'name':'Time','type':'int', 'value':'20'},
                {'name':'Temperature','type':'int','value':'300'},
                {'name':'Ar Flow','type':'int','value':'75'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 5','type':'group','children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 6','type':'group','children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 7','type':'group','children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 8','type':'group','children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'}
            ]},
            {'name':'Segment 9','type':'group','children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]},
            {'name':'Segment 10','type':'group','children':[
                {'name':'Time','type':'int', 'value':'0'},
                {'name':'Temperature','type':'int','value':'25'},
                {'name':'Ar Flow','type':'int','value':'0'},
                {'name':'H2S Flow','type':'int','value':'0'},
                {'name':'Wait for','type':'list','limits':['Time','Temp']}
            ]}
        ]

        self.p = Parameter.create(name='self.params',type='group',children=self.params)
        self.setParameters(self.p,showTop=False)

    def getValue(self,segment:int, branch, child):
        return self.p.param(f'Segment {segment}',branch,child).value()