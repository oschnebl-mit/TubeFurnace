import sys,qdarkstyle, logging
from time import time
from PyQt5 import QtGui,QtCore
import PyQt5.QtWidgets as qw 
import pyqtgraph as pg
import numpy as np

from TubeFurnaceThreads import PressureGauge, MFCControl, FurnaceControl

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
        self.mainbox.setLayout(layout)  # set the layout

        self.tempPlot = TempLoggingPlot('Furnace Temperature','C','#08F7FE')
        self.pressurePlot = BasicLoggingPlot('Pressure','Torr','#FE53BB')


        self.startLoggingButton = qw.QPushButton("Start Logging")
        self.setTempButton = qw.QPushButton("Set Temperature")
        self.delayInputLabel = qw.QLabel('Logging Interval (s):')
        self.delayInput = qw.QLineEdit('10')
        self.delayInput.setValidator(QtGui.QIntValidator())

        self.startLoggingButton.clicked.connect(self.startThreads)
        self.delayInput.returnPressed.connect(self.updateDelay)

        ## grid layout adds as                   r c rs cs (last 2 are rowspan, colspan)
        layout.addWidget(self.startLoggingButton,0,0,1, 1)
        layout.addWidget(self.setTempButton,     1,0,1, 1)
        layout.addWidget(self.delayInputLabel,   2,0,1, 1)
        layout.addWidget(self.delayInput,        3,0,1, 1)

        layout.addWidget(self.tempPlot,          0,1,1, 1)
        layout.addWidget(self.pressurePlot,      2,1,2, 1)

        for r in range(4):
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

