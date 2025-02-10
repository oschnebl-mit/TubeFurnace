import sys
import numpy as np
from time import time
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

# def updateViews(pp1,pp2):
#     pp2.setGeometry(pp1.getViewBox().sceneBoundingRect())
#     pp2.linkedViewChanged(pp1.getViewBox(), pp2.XAxis)


class TubeFillWindow(pg.GraphicsLayoutWidget):
    ## now create a new window while we do the tube filling
    ## TODO add a keyboard interrupt

    def __init__(self):
        super().__init__()
        self.resize(1000,600)
        self.setWindowTitle('Bring Tube to Atmospheric Pressure')

        self.p1 = self.addPlot(title="Pressure/Flow")
        # self.p1.setYRange(0,800)
        self.p1.setLabel('left',"Pressure",units = 'Torr')
        ## create a new ViewBox, link the right axis to its coordinate system
        self.p2 = pg.ViewBox()
        self.p1.showAxis('right')
        self.p1.scene().addItem(self.p2)
        self.p1.getAxis('right').linkToView(self.p2)
        self.p2.setXLink(self.p1)
        self.p1.setLabel('right',"Ar Flow", units='sccm')

        self.updateViews()
        self.p1.getViewBox().sigResized.connect(self.updateViews)

        self._do_fill()

        # ########## troubleshooting: fill in example data
        # self.tube_pressure_trace = self.p1.plot(pen='y')
        # self.sccm_Ar_trace = pg.PlotCurveItem(pen='r')
        # self.p2.addItem(self.sccm_Ar_trace)
        # self.tube_pressure_trace.setData(np.linspace(0,100),np.linspace(0,750))
        # self.sccm_Ar_trace.setData(np.linspace(0,100,20),[0,10,10,10,100, 100,100,100,100,100,  100,100,100,100,100,  100,100,100,100,100])
        
    def updateViews(self):
            self.p2.setGeometry(self.p1.getViewBox().sceneBoundingRect())
            self.p2.linkedViewChanged(self.p1.getViewBox(), self.p2.XAxis)

    def update_plot(self,stop_pressure=700):
        # global tube_pressure_trace, sccm_Ar_trace, tcurr, tube_pressure_data, sccm_Ar_data,timer
        tcurr = time() - self.t0
        actual_tube_pressure = self.tube_pressure_data[-1] ## in practice this would be a measurement
        if actual_tube_pressure >= stop_pressure:
            Ar_flow = 0 ## in practice this would set the MFC
            self.timer.stop()
        elif tcurr <= 5:
            Ar_flow = 10
        elif tcurr > 5:
            Ar_flow = 100

        self.tube_pressure_data.append(actual_tube_pressure+Ar_flow)
        self.sccm_Ar_data.append(Ar_flow)
        self.time_data.append(tcurr)
        
        self.tube_pressure_trace.setData(self.time_data,self.tube_pressure_data)
        self.sccm_Ar_trace.setData(self.time_data,self.sccm_Ar_data)

        # print(tcurr)


    def _do_fill(self):
        self.tube_pressure_trace = self.p1.plot(pen='y')
        self.sccm_Ar_trace = pg.PlotCurveItem(pen='r')
        self.p2.addItem(self.sccm_Ar_trace)

        self.tube_pressure_data = [0]
        self.sccm_Ar_data = [0]
        self.time_data = [0]

        self.t0 = time()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(1000)

class MyMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('Example Main Window')
        self.btn = QtWidgets.QPushButton('Fill Tube',self)
        self.setCentralWidget(self.btn)

        self.btn.clicked.connect(self.launch_tube_fill_window)
        self.show()

    def launch_tube_fill_window(self):
        self.new_window = TubeFillWindow()
        self.new_window.show()
        # self.hide()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyMainWindow()
    sys.exit(app.exec())