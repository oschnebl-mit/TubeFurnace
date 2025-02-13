import sys, logging
from time import time, sleep
from PyQt5 import QtGui,QtCore
import PyQt5.QtWidgets as qw 
import pyqtgraph as pg
import numpy as np

from TubeFurnaceThreads import PressureGauge, MFCControl, FurnaceControl
from TubeFurnaceParams import ProcessParams, OtherParams

class MainControlWindow(qw.QMainWindow):
    def __init__(self, logger, testing = False):
        super().__init__()
        self.testing = testing
        self.logger = logger
        self.setWindowTitle('Control Panel')

        self.resize(1280,720) # non-maximized state

        if self.testing == False:
            self.showMaximized()

        self.initUI()
        self.delay = int(self.delayInput.text())
        self.initThreads()
        self.show()

    def initUI(self):
        ## Create an empty box to hold all the following widgets
        self.mainbox = qw.QWidget()
        self.setCentralWidget(self.mainbox)  # Put it in the center of the main window
        layout = qw.QGridLayout()  # All the widgets will be in a grid in the main box
        self.mainbox.setLayout(layout)  # set the layout\

        ## ~~ Colors ~~ ####
        self.pressurePen = pg.mkPen(color='#5DB4B7',width=2)
        self.flowPen = pg.mkPen(color='#DFC245',width=2)
        self.tempPen = pg.mkPen(color='#CC3300',width=3)

        self.h2sColor = '#DFC245'
        self.arColor = '#C1DE55'
        self.pressureColor = '#5DB4B7'
        self.tempColor = '#CC3300'

        ########################

        self.tree = ProcessParams()
        self.othertree = OtherParams()

        self.tempPlot = TempLoggingPlot('Temperature','C',self.tempColor)
        # print('made temp plot')
        self.pressurePlot = BasicLoggingPlot('Pressure','Torr',self.pressureColor)
        # print('made pressure plot')
        self.flowPlot = FlowLoggingPlot('Flow','sccm',self.arColor,self.h2sColor)
        # print('made flow plot')
        self.currentProcessPlot = pg.PlotWidget()
        # print('made empty CPP')
        self.cp2 = None ## second trace on current process plot
        # print('made empty CP2')

        self.startLoggingButton = qw.QPushButton("Start Logging") ## in the future make this a toggle?
        self.fillButton = qw.QPushButton("Bring tube to atmospheric pressure")
        self.startProcessButton = qw.QPushButton("Start Anneal")
        self.abortProcessButton = qw.QPushButton("Abort Process")
        self.delayInputLabel = qw.QLabel('Logging Interval (s):')
        self.delayInput = qw.QLineEdit('10')
        self.delayInput.setValidator(QtGui.QIntValidator())

        self.othertree.log_interval_change.connect(self.updateDelay)

        self.startLoggingButton.clicked.connect(self.startThreads)
        self.fillButton.clicked.connect(self.fillTube)
        self.startProcessButton.clicked.connect(self.runProcess)
        self.abortProcessButton.clicked.connect(self.abortProcess)
        self.delayInput.returnPressed.connect(self.updateDelay)

        ## grid layout adds as                   r c rs cs (last 2 are rowspan, colspan)
        layout.addWidget(self.tree,              0,0,6, 1)
        layout.addWidget(self.currentProcessPlot,7,0,6, 2)

        layout.addWidget(self.othertree,         0,1,3, 1)
        layout.addWidget(self.startLoggingButton,3,1,1, 1)
        # layout.addWidget(self.delayInputLabel,   1,1,1, 1)
        # layout.addWidget(self.delayInput,        2,1,1, 1)
        layout.addWidget(self.startProcessButton,4,1,1, 1)
        layout.addWidget(self.fillButton,        5,1,1, 1)
        layout.addWidget(self.abortProcessButton,6,1,1, 1)

        layout.addWidget(self.tempPlot,          0,2,4, 1)
        layout.addWidget(self.pressurePlot,      4,2,5, 1)
        layout.addWidget(self.flowPlot,          9,2,4, 1)

        for r in range(12):
            layout.setRowStretch(r,1)

        

    def initThreads(self):
        self.MFC = MFCControl(logger=self.logger,delay=self.delay,testing=self.testing)
        self.PGauge = PressureGauge(overpressure_limit=800,logger=self.logger,delay=self.delay,testing=self.testing)
        self.Furnace = FurnaceControl(logger=self.logger,delay=self.delay,testing=self.testing)

        self.PGauge.overpressure_error.connect(self.abortProcess)
        self.PGauge.new_pressure_data.connect(self.pressurePlot.update)
        self.Furnace.new_temp_data.connect(self.tempPlot.update) 
        self.MFC.new_Ar_data.connect(self.flowPlot.updateAr)
        self.MFC.new_H2S_data.connect(self.flowPlot.updateH2S)

    def startThreads(self):
        self.MFC.start()
        self.PGauge.start()
        self.Furnace.start() ## this is just logging the temperature

    def abortProcess(self):
        ''' Set furnace mode to reset and all gas flows to 0
        Nothing toggles so fine to run repeatedly '''
        self.Furnace.stopFurance() 
        self.MFC.stop_all_gas_flows()
        if self.timer is not None:
            print('stopping timer')
            self.timer.stop()

    def runProcess(self):
        ## for programFurnace need to construct a list of tuples: (SP, TM)
        furnace_params = []
        for si in range(1,len(self.tree.p.children())):
            # if self.tree.getValue(si,'Time') == 0:
            #     break
            furnace_params.append((self.tree.getValue(si,'Temperature'),self.tree.getValue(si,'Time')))
        self.Furnace.programFurnace(furnace_params)

        ## start the furnace running the program defined above
        self.Furnace.startFurnace() 
        for si in range(1,len(self.tree.children())): ## TypeError: object of type 'builtin_function_or_method' has no len()
            ## Add condition to finish if segment is all zeros
            if self.tree.getValue(si,'Wait for') == 'Time':
                self.MFC.set_sccm('Ar',int(self.tree.getValue(si,'Ar Flow')))
                self.MFC.set_sccm('H2S',int(self.tree.getValue(si,'H2S Flow')))
                sleep(int(self.tree.getValue(si,'Time')*60)) ## in minutes
            elif self.tree.getValue(si,'Wait for') == 'Temp':
                self.MFC.set_sccm('Ar',int(self.tree.getValue(si,'Ar Flow')))
                self.MFC.set_sccm('H2S',int(self.tree.getValue(si,'H2S Flow')))
                self.waitForTemp(int(self.tree.getValue(si,'Temperature')))

    def waitForTemp(self, temperature, tolerance = 5):

        while True:
            currentTemp = self.Furnace.getAllTemperatures()[1] ## zone 2
            currentDelta = currentTemp - temperature
            if abs(currentDelta) < tolerance:
                break
            sleep(60)

    def fillTube(self):
        ## Flow Ar until tube is at atmospheric pressure
        print("Fill tube with Ar")
        print(self.othertree.getFillValue('Approach Pressure (Torr)'))
        # self.stopPressure = self.othertree.getValue('Fill Parameters','Fill Pressure (Torr)')
        self.approachPressure = 700
        self.initFlow = 100
        self.finalFlow = 1000

        ''' For demo mode: looks like the tube furnace purge plot, displays updating placeholder data, responds to fill pressure and stop button or pressure condition'''
        self.currentProcessPlot.clear()
        if self.cp2 is not None:
            self.cp2.clear()
        
        self.currentProcessPlot.setLabel('left',"Pressure",units = 'Torr',color=self.pressureColor,**{'font-size': '12pt'})
        self.currentProcessPlot.setLabel('bottom','Time',units='s',color='#e0e0e0',**{'font-size':'12pt'})
        ### for second trace #######
        self.cp2 = pg.ViewBox()
        self.currentProcessPlot.showAxis('right')
        self.currentProcessPlot.scene().addItem(self.cp2)
        self.currentProcessPlot.getAxis('right').linkToView(self.cp2)
        self.cp2.setXLink(self.currentProcessPlot)
        self.currentProcessPlot.setLabel('right',"Ar Flow",units='sccm',color=self.arColor,**{'font-size':'12pt'})
        self.updateViews()
        self.currentProcessPlot.getViewBox().sigResized.connect(self.updateViews)
        #################

        self.tube_pressure_trace = self.currentProcessPlot.plot(pen=self.pressurePen)
        self.sccm_Ar_trace = pg.PlotCurveItem(pen=self.flowPen)
        self.cp2.addItem(self.sccm_Ar_trace)

        self.tube_pressure_data = [0]
        self.sccm_Ar_data=[0]
        self.time_data = [0]
        self.t0 = time()

        self.timer = QtCore.QTimer()
        if self.testing:
            self.timer.timeout.connect(self.update_fill_plot_demo)
        else:
            self.timer.timeout.connect(self.update_fill_plot)
        self.timer.start(1000)

    def updateViews(self):
            self.cp2.setGeometry(self.currentProcessPlot.getViewBox().sceneBoundingRect())
            self.cp2.linkedViewChanged(self.currentProcessPlot.getViewBox(), self.cp2.XAxis)

    def update_fill_plot_demo(self):
        ''' For demo mode: updates with self-generated data, stops on pressure condition'''
        # self.stopPressure = int(self.purgePressureInput.text())
        self.stopPressure = 750
        tcurr = time() - self.t0
        actual_tube_pressure = self.tube_pressure_data[-1]
        if actual_tube_pressure >= self.stopPressure:
            Ar_flow = 0
            self.timer.stop()
        elif tcurr <= 5:
            Ar_flow = 10
        elif tcurr > 5:
            Ar_flow = 100
        
        self.tube_pressure_data.append(actual_tube_pressure+Ar_flow)
        self.sccm_Ar_data.append(Ar_flow)
        self.time_data.append(tcurr)
        tcurr += 1
        
        self.tube_pressure_trace.setData(self.time_data, self.tube_pressure_data)
        self.sccm_Ar_trace.setData(self.time_data,self.sccm_Ar_data)

    def update_fill_plot(self):
        # self.stopPressure = int(self.purgePressureInput.text())
        tcurr = time() - self.t0
        actual_tube_pressure = self.PGauge.getPressure()
        if actual_tube_pressure >= self.stopPressure:
            self.MFC.set_sccm('Ar',0)
            self.logger.info(f'Reached {self.stopPressure} Torr, stopping Ar flow')
            self.timer.stop()
        elif actual_tube_pressure >= self.approachPressure:
            self.MFC.set_sccm('Ar',self.initFlow)
        elif tcurr <= 5:
            self.MFC.set_sccm('Ar',self.initFlow)
            self.logger.info(f'Setting Ar to initial flow: {self.initFlow} sccm')
        elif tcurr > 5:
            self.MFC.set_sccm('Ar',self.finalFlow)
            self.logger.info(f'Setting Ar to {self.finalFlow} sccm')
        
        self.tube_pressure_data.append(actual_tube_pressure)
        self.sccm_Ar_data.append(Ar_flow)
        self.time_data.append(tcurr)
                
        self.tube_pressure_trace.setData(self.time_data, self.tube_pressure_data)
        self.sccm_Ar_trace.setData(self.time_data,self.sccm_Ar_data)
    
    def updateDelay(self):
        # self.delay = int(self.delayInput.text())
        self.delay = self.othertree.p.param('Logging Interval (s)').value()
        print(f'change delay to {self.delay}')

        self.MFC.delay = self.delay
        self.PGauge.delay = self.delay
        self.Furnace.delay = self.delay

class TempLoggingPlot(pg.PlotWidget):
    def __init__(self,ylabel,yunits,color):
        super().__init__()
        self.getPlotItem().showGrid(x=True,y=True,alpha=0.5)
        self.trace_list = []
        for zone in (1,2,3):
            #  pen = pg.mkPen(color='{}{:02x}'.format(color, alpha), width=lw,connect="finite")
            if zone == 2:
                w = 4
                alpha = 250
            else:
                w = 3
                alpha = 100
            trace = self.plot(x=[time()],y=[1],pen=pg.mkPen(color='{}{:02x}'.format(color, alpha),width=w))
            # print(f'made trace {zone} for temp logging plot')
            self.trace_list.append(trace)
        self.setLabel('left',ylabel,units=yunits,color=color)
    def update(self,new_data):
        # new data is a list of floats
        for i,trace in enumerate(self.trace_list):
            xdata,ydata = trace.getData()
            xdata = np.append(xdata,time())
            ydata = np.append(ydata,new_data[i])
            trace.setData(xdata,ydata)

class FlowLoggingPlot(pg.PlotWidget):
    def __init__(self,ylabel,yunits,arColor,h2sColor,alpha = 200):
        super().__init__()
        self.getPlotItem().showGrid(x=True,y=True,alpha=0.5)
        self.addLegend()
        self.setLabel('left',ylabel,units=yunits,color=arColor)
        self.arTrace = self.plot(x=[time()],y=[1],pen=pg.mkPen(color='{}{:02x}'.format(arColor, alpha),width=3),name='Ar')
        self.h2sTrace = self.plot(x=[time()],y=[0],pen=pg.mkPen(color='{}{:02x}'.format(h2sColor, alpha),width=3),name='H2S')
        

    def updateH2S(self,new_data):
        xdata,ydata = self.h2sTrace.getData()
        # print(old_data)
        xdata = np.append(xdata,time())
        ydata = np.append(ydata,new_data)
        self.h2sTrace.setData(x=xdata,y=ydata)

    def updateAr(self,new_data):
        xdata,ydata = self.arTrace.getData()
        # print(old_data)
        xdata = np.append(xdata,time())
        ydata = np.append(ydata,new_data)
        self.arTrace.setData(x=xdata,y=ydata)





class BasicLoggingPlot(pg.PlotWidget):
    def __init__(self,ylabel,yunits,color):
        super().__init__()
        # self.plot = pg.PlotWidget()
        self.getPlotItem().showGrid(x=True, y=True, alpha=1)
        self.trace = self.plot(x=[time()],y=[1],pen=pg.mkPen(color=color,width=2))
        # print('made trace on Basic Logging Plot')
        self.setLabel('left',ylabel,units=yunits,color=color)

    def update(self,new_data):
        xdata,ydata = self.trace.getData()
        # print(old_data)
        xdata = np.append(xdata,time())
        ydata = np.append(ydata,new_data)
        self.trace.setData(x=xdata,y=ydata)

class LoggingPlot(qw.QWidget):
    def __init__(self, plot_title, color):
        super().__init__()
        masterLayout = qw.QVBoxLayout()
        self.pen = pg.mkPen(color, width=1.25)
        layout = qw.QVBoxLayout()
        self.group = qw.QGroupBox(plot_title)
        self.plot = pg.PlotWidget()
        for item in dataItems:
            self.trace_list.append(pg.PlotCurveItem(pen=self.pen)) ## what if I want different pens?
        self.plot.getPlotItem().showGrid(x=True, y=True, alpha=1)
        if "qdarkstyle" in sys.modules:
            self.plot.setBackground((25, 35, 45))

        self.group.setLayout(layout)
        layout.addWidget(self.plot)
        masterLayout.addWidget(self.group)

        self.setLayout(masterLayout)

    def update_plot(self,new_data):
        ## Let's say new_data is a tuple or a float
        if len(new_data) == 0:
            xdata,ydata = self.trace.getData()
            xdata = np.append(xdata,time())
            ydata = np.append(ydata,new_data)
            self.trace.setData(x=xdata, y=ydata)
        elif len(new_data) != len(self.plot.listDataItems()):
                return
        else:
            for trace in self.plot.listDataItems():
                color = trace.opts['pen'].color().name()
                (x_data, y_data) = trace.getData()
                xdata = np.append(xdata,time())
                ydata = np.append(ydata,new_data)
                trace.setData(x=xdata, y=ydata)
        # self.plot.getViewBox().autoRange()

if __name__ == "__main__":

    logger = logging.getLogger(__name__)
    logger.addHandler(logging.NullHandler())
    app = qw.QApplication(sys.argv)
    try:
        import qdarkstyle
        app.setStyleSheet(qdarkstyle.load_stylesheet())
    except:
        pass

    window = MainControlWindow(logger = logger, testing = True)
    
    sys.exit(app.exec())

