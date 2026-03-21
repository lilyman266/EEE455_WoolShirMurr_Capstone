#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Combined BPSK Transceiver - TX/RX switchable via XML-RPC
# Control from Python:
#   import xmlrpc.client
#   proxy = xmlrpc.client.ServerProxy("http://localhost:8080")
#   proxy.set_mode(1)  # TX
#   proxy.set_mode(0)  # RX

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print("Warning: failed to XInitThreads()")

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio.filter import firdes
import sip
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio import gr
from gnuradio import pdu
from gnuradio import uhd
from gnuradio import zeromq
from gnuradio.qtgui import Range, RangeWidget
from PyQt5 import QtCore
from packaging.version import Version as StrictVersion
import sys
import signal
import time
import threading
from xmlrpc.server import SimpleXMLRPCServer
import gnuradio.fec as fec


class transceiver_bpsk(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "BPSK Transceiver", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("BPSK Transceiver")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "transceiver_bpsk")
        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except:
            pass

        ##################################################
        # Variables
        # mode=0 -> RX, mode=1 -> TX
        ##################################################
        self.mode = 0
        self.sps = sps = 4
        self.samp_rate = samp_rate = 2e6
        self.preamble_size = preamble_size = 512
        self.postamble_size = postamble_size = 64
        self.payload_size = payload_size = 1024
        self.hdr = hdr = digital.header_format_default(digital.packet_utils.default_access_code, 0)
        self.frequency = frequency = 451e6
        self.constel = constel = digital.constellation_bpsk().base()
        self.tx_gain = tx_gain = 44
        self.rx_gain = rx_gain = 44

        ##################################################
        # UHD B210
        ##################################################
        self.uhd_usrp_sink = uhd.usrp_sink(
            ",".join(("", "")),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0, 1)),
            ),
            '',
        )
        self.uhd_usrp_sink.set_samp_rate(samp_rate)
        self.uhd_usrp_sink.set_time_now(uhd.time_spec(time.time()), uhd.ALL_MBOARDS)
        self.uhd_usrp_sink.set_center_freq(frequency, 0)
        self.uhd_usrp_sink.set_antenna('RX2', 0)   # starts in RX mode, sink uses RX2
        self.uhd_usrp_sink.set_gain(tx_gain, 0)

        self.uhd_usrp_source = uhd.usrp_source(
            ",".join(("", "")),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0, 1)),
            ),
        )
        self.uhd_usrp_source.set_samp_rate(samp_rate)
        self.uhd_usrp_source.set_time_now(uhd.time_spec(time.time()), uhd.ALL_MBOARDS)
        self.uhd_usrp_source.set_center_freq(frequency, 0)
        self.uhd_usrp_source.set_antenna('TX/RX', 0)  # starts in RX mode, source uses TX/RX
        self.uhd_usrp_source.set_gain(rx_gain, 0)

        ##################################################
        # TX Blocks
        ##################################################
        self.zeromq_pull_source = zeromq.pull_source(gr.sizeof_char, 1, 'tcp://127.0.0.1:5557', 100, False, -1)
        self.blocks_stream_to_tagged_stream_payload = blocks.stream_to_tagged_stream(gr.sizeof_char, 1, payload_size, "packet_len")
        self.blocks_stream_to_tagged_stream_preamble = blocks.stream_to_tagged_stream(gr.sizeof_char, 1, preamble_size, "packet_len")
        self.blocks_stream_to_tagged_stream_postamble = blocks.stream_to_tagged_stream(gr.sizeof_char, 1, postamble_size, "packet_len")
        self.blocks_vector_source_preamble = blocks.vector_source_b([0xAA], True, 1, [])
        self.blocks_vector_source_postamble = blocks.vector_source_b([0xAA], True, 1, [])
        self.digital_crc32_bb_tx = digital.crc32_bb(False, "packet_len", True)
        self.digital_protocol_formatter = digital.protocol_formatter_bb(hdr, 'packet_len')
        self.blocks_tagged_stream_mux = blocks.tagged_stream_mux(gr.sizeof_char*1, 'packet_len', 0)
        self.digital_constellation_modulator = digital.generic_mod(
            constellation=constel,
            differential=True,
            samples_per_symbol=sps,
            pre_diff_code=True,
            excess_bw=0.35,
            verbose=False,
            log=False,
            truncate=False)
        self.blocks_multiply_const_tx = blocks.multiply_const_cc(0.5)

        # TX selector: input 0 = real signal, input 1 = null source
        # Starts with input 1 (null) since we begin in RX mode
        self.blocks_selector_tx = blocks.selector(gr.sizeof_gr_complex*1, 1, 0)
        self.blocks_selector_tx.set_enabled(True)
        self.blocks_null_source_tx = blocks.null_source(gr.sizeof_gr_complex*1)

        ##################################################
        # RX Blocks
        ##################################################
        # RX selector: output 0 = RX chain, output 1 = null sink
        # Starts with output 0 (RX chain) since we begin in RX mode
        self.blocks_selector_rx = blocks.selector(gr.sizeof_gr_complex*1, 0, 0)
        self.blocks_selector_rx.set_enabled(True)
        self.blocks_null_sink_rx = blocks.null_sink(gr.sizeof_gr_complex*1)

        self.filter_fft_rrc = filter.fft_filter_ccc(1, firdes.root_raised_cosine(1, samp_rate, samp_rate/sps, 0.35, 11*sps), 1)
        self.digital_symbol_sync = digital.symbol_sync_cc(
            digital.TED_SIGNAL_TIMES_SLOPE_ML,
            sps, 0.045, 1.0, 0.1, 1.5, 1,
            constel.base(),
            digital.IR_MMSE_8TAP, 32, [])
        self.digital_costas_loop = digital.costas_loop_cc(3.14/100, len(constel.points()), False)
        self.digital_constellation_decoder = digital.constellation_decoder_cb(constel)
        self.digital_diff_decoder = digital.diff_decoder_bb(len(constel.points()), digital.DIFF_DIFFERENTIAL)
        self.digital_correlate_access_code = digital.correlate_access_code_bb_ts(
            digital.packet_utils.default_access_code, 0, 'packet_len')
        self.blocks_repack_bits = blocks.repack_bits_bb(1, 8, 'packet_len', True, gr.GR_MSB_FIRST)
        self.digital_crc32_bb_rx = digital.crc32_bb(True, 'packet_len', True)
        self.pdu_tagged_stream_to_pdu = pdu.tagged_stream_to_pdu(gr.types.byte_t, 'packet_len')
        self.blocks_message_debug = blocks.message_debug(True)
        self.zeromq_push_sink = zeromq.push_sink(gr.sizeof_char, 1, 'tcp://127.0.0.1:5558', 100, False, -1)

        ##################################################
        # GUI
        ##################################################
        self.qtgui_time_sink_tx = qtgui.time_sink_c(1024, samp_rate, "Transmitted Samples", 1, None)
        self.qtgui_time_sink_tx.set_update_time(0.10)
        self.qtgui_time_sink_tx.set_y_axis(-1.5, 1.5)
        self._qtgui_time_sink_tx_win = sip.wrapinstance(self.qtgui_time_sink_tx.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_time_sink_tx_win)

        self.qtgui_time_sink_rx = qtgui.time_sink_c(256, samp_rate/sps, "Recovered Symbols", 1, None)
        self.qtgui_time_sink_rx.set_update_time(0.10)
        self.qtgui_time_sink_rx.set_y_axis(-1.0, 1.0)
        self._qtgui_time_sink_rx_win = sip.wrapinstance(self.qtgui_time_sink_rx.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_time_sink_rx_win)

        ##################################################
        # TX Connections
        ##################################################
        self.connect((self.zeromq_pull_source, 0), (self.blocks_stream_to_tagged_stream_payload, 0))
        self.connect((self.blocks_stream_to_tagged_stream_payload, 0), (self.digital_crc32_bb_tx, 0))
        self.connect((self.digital_crc32_bb_tx, 0), (self.digital_protocol_formatter, 0))
        self.connect((self.digital_crc32_bb_tx, 0), (self.blocks_tagged_stream_mux, 2))
        self.connect((self.digital_protocol_formatter, 0), (self.blocks_tagged_stream_mux, 1))
        self.connect((self.blocks_vector_source_preamble, 0), (self.blocks_stream_to_tagged_stream_preamble, 0))
        self.connect((self.blocks_vector_source_postamble, 0), (self.blocks_stream_to_tagged_stream_postamble, 0))
        self.connect((self.blocks_stream_to_tagged_stream_preamble, 0), (self.blocks_tagged_stream_mux, 0))
        self.connect((self.blocks_stream_to_tagged_stream_postamble, 0), (self.blocks_tagged_stream_mux, 3))
        self.connect((self.blocks_tagged_stream_mux, 0), (self.digital_constellation_modulator, 0))
        self.connect((self.digital_constellation_modulator, 0), (self.blocks_multiply_const_tx, 0))
        self.connect((self.blocks_multiply_const_tx, 0), (self.qtgui_time_sink_tx, 0))
        self.connect((self.blocks_multiply_const_tx, 0), (self.blocks_selector_tx, 0))
        self.connect((self.blocks_null_source_tx, 0), (self.blocks_selector_tx, 1))
        self.connect((self.blocks_selector_tx, 0), (self.uhd_usrp_sink, 0))

        ##################################################
        # RX Connections
        ##################################################
        self.connect((self.uhd_usrp_source, 0), (self.blocks_selector_rx, 0))
        self.connect((self.blocks_selector_rx, 0), (self.filter_fft_rrc, 0))
        self.connect((self.blocks_selector_rx, 1), (self.blocks_null_sink_rx, 0))
        self.connect((self.filter_fft_rrc, 0), (self.digital_symbol_sync, 0))
        self.connect((self.digital_symbol_sync, 0), (self.digital_costas_loop, 0))
        self.connect((self.digital_costas_loop, 0), (self.digital_constellation_decoder, 0))
        self.connect((self.digital_costas_loop, 0), (self.qtgui_time_sink_rx, 0))
        self.connect((self.digital_constellation_decoder, 0), (self.digital_diff_decoder, 0))
        self.connect((self.digital_diff_decoder, 0), (self.digital_correlate_access_code, 0))
        self.connect((self.digital_correlate_access_code, 0), (self.blocks_repack_bits, 0))
        self.connect((self.blocks_repack_bits, 0), (self.digital_crc32_bb_rx, 0))
        self.connect((self.digital_crc32_bb_rx, 0), (self.pdu_tagged_stream_to_pdu, 0))
        self.connect((self.digital_crc32_bb_rx, 0), (self.zeromq_push_sink, 0))
        self.msg_connect((self.pdu_tagged_stream_to_pdu, 'pdus'), (self.blocks_message_debug, 'print'))

        ##################################################
        # XML-RPC Server
        ##################################################
        self.xmlrpc_server = SimpleXMLRPCServer(
            ("localhost", 8080),
            allow_none=True,
            logRequests=False
        )
        self.xmlrpc_server.register_function(self.set_mode, "set_mode")
        self.xmlrpc_server.register_function(self.get_mode, "get_mode")
        self.xmlrpc_thread = threading.Thread(
            target=self.xmlrpc_server.serve_forever,
            daemon=True
        )
        self.xmlrpc_thread.start()
        print("XML-RPC server started on port 8080", flush=True)
        print("FLOWGRAPH_READY", flush=True)

    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "transceiver_bpsk")
        self.settings.setValue("geometry", self.saveGeometry())
        self.xmlrpc_server.shutdown()
        self.stop()
        self.wait()
        event.accept()

    def get_mode(self):
        return self.mode

    def set_mode(self, mode):
        self.mode = mode
        if mode == 1:
            self.uhd_usrp_sink.set_antenna('TX/RX', 0)
            self.uhd_usrp_source.set_antenna('RX2', 0)
            self.blocks_selector_tx.set_input_index(0)
            self.blocks_selector_rx.set_output_index(1)
        else:
            self.uhd_usrp_sink.set_antenna('RX2', 0)
            self.uhd_usrp_source.set_antenna('TX/RX', 0)
            self.blocks_selector_rx.set_output_index(0)
            self.blocks_selector_tx.set_input_index(1)
            time.sleep(0.5)  # give antenna switch time to settle
        print(f"Mode switched to: {'TX' if mode == 1 else 'RX'}", flush=True)

    def get_samp_rate(self):
        return self.samp_rate

    def get_frequency(self):
        return self.frequency

    def set_frequency(self, frequency):
        self.frequency = frequency
        self.uhd_usrp_sink.set_center_freq(frequency, 0)
        self.uhd_usrp_source.set_center_freq(frequency, 0)

    def get_tx_gain(self):
        return self.tx_gain

    def set_tx_gain(self, tx_gain):
        self.tx_gain = tx_gain
        self.uhd_usrp_sink.set_gain(tx_gain, 0)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.uhd_usrp_source.set_gain(rx_gain, 0)


def main(top_block_cls=transceiver_bpsk, options=None):
    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()
    tb.start()
    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()