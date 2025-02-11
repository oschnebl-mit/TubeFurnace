import sys,qdarkstyle, logging
from time import time, sleep
from PyQt5 import QtGui,QtCore
import PyQt5.QtWidgets as qw 
import pyqtgraph as pg
import numpy as np

from TubeFurnaceThreads import PressureGauge, MFCControl, FurnaceControl
from TubeFurnaceParams import TubeFurnaceParams

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
        self.pressurePen = pg.mkPen(color='#FE53BB',width=2)
        self.flowPen = pg.mkPen(color='#F5D300',width=2)
        self.tempPen = pg.mkPen(color='#08F7FE',width=2)

        ########################

        self.tree = TubeFurnaceParams()

        self.tempPlot = TempLoggingPlot('Furnace Temperature','C','#08F7FE')
        self.pressurePlot = BasicLoggingPlot('Pressure','Torr','#FE53BB')
        self.flowPlot = BasicLoggingPlot('Flow','sccm','#08F7FE')
        self.currentProcessPlot = pg.PlotWidget()
        self.cp2 = None ## second trace on current process plot


        self.startLoggingButton = qw.QPushButton("Start Logging") ## in the future make this a toggle?
        self.fillButton = qw.QPushButton("Bring tube to atmospheric pressure")
        self.startProcessButton = qw.QPushButton("Start Anneal")
        self.abortProcessButton = qw.QPushButton("Abort Process")
        self.delayInputLabel = qw.QLabel('Logging Interval (s):')
        self.delayInput = qw.QLineEdit('10')
        self.delayInput.setValidator(QtGui.QIntValidator())

        self.startLoggingButton.clicked.connect(self.startThreads)
        self.fillButton.clicked.connect(self.fillTube)
        self.startProcessButton.clicked.connect(self.runProcess)
        self.abortProcessButton.clicked.connect(self.abortProcess)
        self.delayInput.returnPressed.connect(self.updateDelay)

        ## grid layout adds as                   r c rs cs (last 2 are rowspan, colspan)
        layout.addWidget(self.tree,              0,0,5, 1)
        layout.addWidget(self.currentProcessPlot,6,0,3, 2)

        layout.addWidget(self.startLoggingButton,0,1,1, 1)
        layout.addWidget(self.delayInputLabel,   1,1,1, 1)
        layout.addWidget(self.delayInput,        2,1,1, 1)
        layout.addWidget(self.startProcessButton,3,1,1, 1)
        layout.addWidget(self.fillButton,        4,1,1, 1)
        layout.addWidget(self.abortProcessButton,5,1,1, 1)

        layout.addWidget(self.tempPlot,          0,2,3, 1)
        layout.addWidget(self.pressurePlot,      3,2,3, 1)
        layout.addWidget(self.flowPlot,          6,2,3, 1)

        for r in range(9):
            layout.setRowStretch(r,1)

        

    def initThreads(self):
        self.MFC = MFCControl(logger=self.logger,delay=self.delay,testing=self.testing)
        self.PGauge = PressureGauge(logger=self.logger,delay=self.delay,testing=self.testing)
        self.Furnace = FurnaceControl(logger=self.logger,delay=self.delay,testing=self.testing)

        self.PGauge.new_pressure_data.connect(self.pressurePlot.update)
        self.Furnace.new_temp_data.connect(self.tempPlot.update) ## holding off because this is a list

    def startThreads(self):
        self.MFC.start()
        self.PGauge.start()
        self.Furnace.start()

    def abortProcess(self):
        # self.Furnace.stopFurance()
        self.MFC.stop_all_gas_flows()
        if self.timer is not None:
            print('stopping timer')
            self.timer.stop()

    def runProcess(self):
        ## for programFurnace need to construct a list of tuples: (SP, TM)
        furnace_params = []
        for si in range(len(self.tree.children)):
            furnace_params.append((self.tree.getValue(si,'Temperature'),self.tree.getValue(si,'Time')))
        self.Furnace.programFurnace(furnace_params)

        self.Furnace.start()
        for si in range(len(self.tree.children)):
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
        self.stopPressure = 750
        self.approachPressure = 700
        self.initFlow = 100
        self.finalFlow = 1000

        ''' For demo mode: looks like the tube furnace purge plot, displays updating placeholder data, responds to fill pressure and stop button or pressure condition'''
        self.currentProcessPlot.clear()
        if self.cp2 is not None:
            self.cp2.clear()
        
        self.currentProcessPlot.setLabel('left',"Pressure",units = 'Torr',color='#FE53BB',**{'font-size': '12pt'})
        self.currentProcessPlot.setLabel('bottom','Time',units='s',color='#e0e0e0',**{'font-size':'12pt'})
        ### for second trace #######
        self.cp2 = pg.ViewBox()
        self.currentProcessPlot.showAxis('right')
        self.currentProcessPlot.scene().addItem(self.cp2)
        self.currentProcessPlot.getAxis('right').linkToView(self.cp2)
        self.cp2.setXLink(self.currentProcessPlot)
        self.currentProcessPlot.setLabel('right',"Ar Flow",units='sccm',color='#F5D300',**{'font-size':'12pt'})
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
        self.delay = int(self.delayInput.text())
        print(f'change delay to {self.delay}')

        self.MFC.delay = self.delay
        self.PGauge.delay = self.delay
        self.Furnace.delay = self.delay

class TempLoggingPlot(pg.PlotWidget):
    def __init__(self,ylabel,yunits,color):
        super().__init__()
        self.getPlotItem().showGrid(x=True,y=True,alpha=1)
        self.trace_list = []
        for zone in (1,2,3):
            trace = self.plot(x=[time()],y=[1],pen=pg.mkPen(color=color,width=2))
            self.trace_list.append(trace)
        self.setLabel('left',ylabel,units=yunits,color=color)
    def update(self,new_data):
        # new data is a list of floats
        for i,trace in enumerate(self.trace_list):
            xdata,ydata = trace.getData()
            xdata = np.append(xdata,time())
            ydata = np.append(ydata,new_data[i])
            trace.setData(xdata,ydata)

class BasicLoggingPlot(pg.PlotWidget):
    def __init__(self,ylabel,yunits,color):
        super().__init__()
        # self.plot = pg.PlotWidget()
        self.getPlotItem().showGrid(x=True, y=True, alpha=1)
        self.trace = self.plot(x=[time()],y=[1],pen=pg.mkPen(color=color,width=2))
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
        self.trace = self.plot.plot(x=[],y=[],pen=self.pen)
        self.trace.setSkipFiniteCheck(True)
        self.plot.getPlotItem().showGrid(x=True, y=True, alpha=1)
        if "qdarkstyle" in sys.modules:
            self.plot.setBackground((25, 35, 45))

        self.group.setLayout(layout)
        layout.addWidget(self.plot)
        masterLayout.addWidget(self.group)

        self.setLayout(masterLayout)

    def update_plot(self,new_data):
        xdata,ydata = self.trace.getData()
        xdata = np.append(xdata,time())
        ydata = np.append(ydata,new_data)
        self.trace.setData(x=xdata, y=ydata)
        # self.plot.getViewBox().autoRange()

if __name__ == "__main__":

    logger = logging.getLogger(__name__)
    logger.addHandler(logging.NullHandler())
    app = qw.QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet())

    window = MainControlWindow(logger = logger, testing = True)
    
    sys.exit(app.exec())

