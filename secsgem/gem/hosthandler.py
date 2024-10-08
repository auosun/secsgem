#####################################################################
# hosthandler.py
#
# (c) Copyright 2013-2024, Benjamin Parzella. All rights reserved.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#####################################################################
"""Handler for GEM host."""

from __future__ import annotations

import collections
import typing

import secsgem.common

from .handler import GemHandler

if typing.TYPE_CHECKING:
    import secsgem.secs


class GemHostHandler(GemHandler):
    """Baseclass for creating host models. Inherit from this class and override required functions."""

    def __init__(self, settings: secsgem.common.Settings):
        """Initialize a gem host handler.

        Args:
            settings: communication settings

        """
        GemHandler.__init__(self, settings)

        self.is_host = True

        self.report_subscriptions: dict[int | str, list[int | str]] = {}

    def clear_collection_events(self) -> None:
        """Clear all collection events."""
        self._logger.info("Clearing collection events")

        # clear subscribed reports
        self.report_subscriptions = {}

        # disable all ceids
        self.disable_ceids()

        # delete all reports
        self.disable_ceid_reports()

    def subscribe_collection_event(self, ceid: int | str, dvs: list[int | str], report_id: int | str | None = None):
        """Subscribe to a collection event.

        Args:
            ceid: ID of the collection event
            dvs: DV IDs to add for collection event
            report_id: optional - ID for report, autonumbering if None

        """
        self._logger.info("Subscribing to collection event %s", ceid)

        if report_id is None:
            report_id = self._report_id_counter
            self._report_id_counter += 1

        # note subscribed reports
        self.report_subscriptions[report_id] = dvs

        # create report
        self.send_and_waitfor_response(
            self.stream_function(2, 33)({"DATAID": 0, "DATA": [{"RPTID": report_id, "VID": dvs}]}),
        )

        # link event report to collection event
        self.send_and_waitfor_response(
            self.stream_function(2, 35)({"DATAID": 0, "DATA": [{"CEID": ceid, "RPTID": [report_id]}]}),
        )

        # enable collection event
        self.send_and_waitfor_response(self.stream_function(2, 37)({"CEED": True, "CEID": [ceid]}))

    def send_remote_command(self, rcmd: int | str, params: list[str]) -> secsgem.secs.SecsStreamFunction:
        """Send a remote command.

        Args:
            rcmd: Name of command
            params: DV IDs to add for collection event

        Returns:
            response from remote

        """
        self._logger.info("Send RCMD %s", rcmd)

        s2f41 = self.stream_function(2, 41)()
        s2f41.RCMD = rcmd
        if isinstance(params, list):
            for param in params:
                s2f41.PARAMS.append({"CPNAME": param[0], "CPVAL": param[1]})
        elif isinstance(params, collections.OrderedDict):
            for param in params:
                s2f41.PARAMS.append({"CPNAME": param, "CPVAL": params[param]})

        # send remote command
        return self.settings.streams_functions.decode(self.send_and_waitfor_response(s2f41))

    def delete_process_programs(self, ppids: list[int | str]):
        """Delete a list of process program.

        Args:
            ppids: Process programs to delete

        Returns:
            response from remote

        """
        self._logger.info("Delete process programs %s", ppids)

        # send remote command
        return self.settings.streams_functions.decode(
            self.send_and_waitfor_response(self.stream_function(7, 17)(ppids)),
        ).get()

    def get_process_program_list(self):
        """Get process program list.

        Returns:
            response from remote

        """
        self._logger.info("Get process program list")

        # send remote command
        return self.settings.streams_functions.decode(
            self.send_and_waitfor_response(self.stream_function(7, 19)()),
        ).get()

    def go_online(self):
        """Set control state to online.

        Returns:
            response text or None if no response text

        """
        self._logger.info("Go online")

        # send remote command
        resp = self.settings.streams_functions.decode(self.send_and_waitfor_response(self.stream_function(1, 17)()))
        if resp is None:
            return None

        return resp.get()

    def go_offline(self):
        """Set control state to offline.

        Returns:
            response text or None if no response text

        """
        self._logger.info("Go offline")

        # send remote command
        return self.settings.streams_functions.decode(
            self.send_and_waitfor_response(self.stream_function(1, 15)()),
        ).get()

    def enable_alarm(self, alid: int | str):
        """Enable alarm.

        Args:
            alid: alarm id to enable

        Returns:
            response from remote

        """
        self._logger.info("Enable alarm %d", alid)

        return self.settings.streams_functions.decode(
            self.send_and_waitfor_response(
                self.stream_function(5, 3)({"ALED": self.settings.data_items.ALED.ENABLE, "ALID": alid}),
            ),
        ).get()

    def disable_alarm(self, alid: int | str):
        """Disable alarm.

        Args:
            alid: alarm id to disable

        Returns:
            response from remote

        """
        self._logger.info("Disable alarm %d", alid)

        return self.settings.streams_functions.decode(
            self.send_and_waitfor_response(
                self.stream_function(5, 3)({"ALED": self.settings.data_items.ALED.DISABLE, "ALID": alid}),
            ),
        ).get()

    def list_alarms(self, alids: list[int | str] | None = None):
        """List alarms.

        Args:
            alids: alarms to list details for

        Returns:
            response from remote

        """
        if alids is None:
            alids = []
            self._logger.info("List all alarms")
        else:
            self._logger.info("List alarms %s", alids)

        return self.settings.streams_functions.decode(
            self.send_and_waitfor_response(self.stream_function(5, 5)(alids)),
        ).get()

    def list_enabled_alarms(self):
        """List enabled alarms.

        Returns:
            response from remote

        """
        self._logger.info("List all enabled alarms")

        return self.settings.streams_functions.decode(
            self.send_and_waitfor_response(self.stream_function(5, 7)()),
        ).get()

    def _on_alarm_received(
        self,
        _handler: secsgem.secs.SecsHandler,
        _alarm_id: int,
        _alarm_code: int,
        _alarm_text: str,
    ):
        """Handle received alarm.

        Args:
            handler: handler the message was received on
            alarm_id: alarm ID
            alarm_code: alarm code
            alarm_text: alarm text

        Returns:
            response to alarm

        """
        return self.settings.data_items.ACKC5.ACCEPTED

    def _on_s05f01(
        self,
        handler: secsgem.secs.SecsHandler,
        message: secsgem.common.Message,
    ) -> secsgem.secs.SecsStreamFunction | None:
        """Handle Stream 5, Function 1, Alarm request.

        Args:
            handler: handler the message was received on
            message: complete message received

        """
        s5f1 = self.settings.streams_functions.decode(message)

        result = self._callback_handler.alarm_received(handler, s5f1.ALID, s5f1.ALCD, s5f1.ALTX)

        self.events.fire(
            "alarm_received",
            {"code": s5f1.ALCD, "alid": s5f1.ALID, "text": s5f1.ALTX, "handler": self.protocol, "peer": self},
        )

        return self.stream_function(5, 2)(result)

    def _on_s06f11(
        self,
        _handler: secsgem.secs.SecsHandler,
        message: secsgem.common.Message,
    ) -> secsgem.secs.SecsStreamFunction | None:
        """Handle Stream 6, Function 11, Event Report Send.

        Args:
            handler: handler the message was received on
            message: complete message received

        """
        function = self.settings.streams_functions.decode(message)

        for report in function.RPT:
            report_dvs = self.report_subscriptions[report.RPTID.get()]
            report_values = report.V.get()

            values = []

            for index, data_value_id in enumerate(report_dvs):
                values.append({"dvid": data_value_id, "value": report_values[index]})

            data = {
                "ceid": function.CEID,
                "rptid": report.RPTID,
                "values": values,
                "handler": self.protocol,
                "peer": self,
            }
            self.events.fire("collection_event_received", data)

        return self.stream_function(6, 12)(0)

    def _on_terminal_received(self, _handler: secsgem.secs.SecsHandler, _terminal_id: int, _text: str):
        """Handle received terminal message.

        Args:
            handler: handler the message was received on
            terminal_id: terminal ID
            text: messsage text

        """
        return self.settings.data_items.ACKC10.ACCEPTED

    def _on_s10f01(
        self,
        handler: secsgem.secs.SecsHandler,
        message: secsgem.common.Message,
    ) -> secsgem.secs.SecsStreamFunction | None:
        """Handle Stream 10, Function 1, Terminal Request.

        Args:
            handler: handler the message was received on
            message: complete message received

        """
        s10f1 = self.settings.streams_functions.decode(message)

        result = self._callback_handler.terminal_received(handler, s10f1.TID, s10f1.TEXT)
        self.events.fire(
            "terminal_received",
            {"text": s10f1.TEXT, "terminal": s10f1.TID, "handler": self.protocol, "peer": self},
        )

        return self.stream_function(10, 2)(result)
