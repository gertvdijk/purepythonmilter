# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from purepythonmilter.api.models import RequestProtocolFlags


def test_request_protocol_flags_default() -> None:
    r = RequestProtocolFlags()
    pf, af = r.encode_to_flags_bitmask()
    expected_pf = (
        0x00000001  # SMFIP_NOCONNECT / call_connect: bool = False
        | 0x00000002  # SMFIP_NOHELO / call_helo: bool = False
        | 0x00000004  # SMFIP_NOMAIL / call_mail_from: bool = False
        | 0x00000008  # SMFIP_NORCPT / call_rcpt_to: bool = False
        # | 0x00000800  # SMFIP_RCPT_REJ / call_rcpt_to_rejected: bool = False
        | 0x00000200  # SMFIP_NODATA / call_data: bool = False
        | 0x00000020  # SMFIP_NOHDRS / call_headers: bool = False
        | 0x00000040  # SMFIP_NOEOH / call_end_of_headers: bool = False
        | 0x00000010  # SMFIP_NOBODY / call_body_chunk: bool = False
        | 0x00000100  # SMFIP_NOUNKNOWN / call_unknown: bool = False
        | 0x00001000  # SMFIP_NR_CONN / reply_connect: bool = False
        | 0x00002000  # SMFIP_NR_HELO / reply_helo: bool = False
        | 0x00004000  # SMFIP_NR_MAIL / reply_mail_from: bool = False
        | 0x00008000  # SMFIP_NR_RCPT / reply_rcpt_to: bool = False
        | 0x00010000  # SMFIP_NR_DATA / reply_data: bool = False
        | 0x00020000  # SMFIP_NR_UNKN / reply_unknown: bool = False
        | 0x00000080  # SMFIP_NR_HDR / SMFIP_NOHREPL / reply_headers: bool = False
        | 0x00040000  # SMFIP_NR_EOH / reply_end_of_headers: bool = False
        | 0x00080000  # SMFIP_NR_BODY / reply_body_chunk: bool = False
        | 0x00000400  # SMFIP_SKIP / can_skip_body_chunks: bool = True
        # | 0x00100000  # SMFIP_HDR_LEADSPC / headers_with_leading_space: bool = False
    )
    expected_af = (
        0x00000000  # Dummy for next lines as comments preserving '|'
        # | 0x00000001  # SMFIF_ADDHDRS
        # | 0x00000002  # SMFIF_CHGBODY
        # | 0x00000004  # SMFIF_ADDRCPT
        # | 0x00000080  # SMFIF_ADDRCPT_PAR
        # | 0x00000008  # SMFIF_DELRCPT
        # | 0x00000010  # SMFIF_CHGHDRS
        # | 0x00000020  # SMFIF_QUARANTINE
        # | 0x00000040  # SMFIF_CHGFROM
        | 0x00000100  # SMFIF_SETSYMLIST
    )

    assert f"{pf:#08x}" == f"{expected_pf:#08x}"
    assert f"{af:#08x}" == f"{expected_af:#08x}"


@pytest.mark.parametrize(
    ("request_obj", "flag_test"),
    [
        pytest.param(
            RequestProtocolFlags(call_rcpt_to_rejected=True),
            0x00000800,  # SMFIP_RCPT_REJ
            id="call_rcpt_to_rejected",
        ),
        pytest.param(
            RequestProtocolFlags(headers_with_leading_space=True),
            0x00100000,  # SMFIP_HDR_LEADSPC
            id="headers_with_leading_space",
        ),
    ],
)
def test_request_protocol_flags_non_default_protocol(
    request_obj: RequestProtocolFlags, flag_test: int
) -> None:
    pf, _ = request_obj.encode_to_flags_bitmask()
    assert pf & flag_test


@pytest.mark.parametrize(
    ("request_obj", "flag_test"),
    [
        pytest.param(
            RequestProtocolFlags(can_add_headers=True),
            0x00000001,  # SMFIF_ADDHDRS
            id="can_add_headers",
        ),
        pytest.param(
            RequestProtocolFlags(can_change_body=True),
            0x00000002,  # SMFIF_CHGBODY
            id="can_change_body",
        ),
        pytest.param(
            RequestProtocolFlags(can_add_recipients=True),
            0x00000004,  # SMFIF_ADDRCPT
            id="can_add_recipients",
        ),
        pytest.param(
            RequestProtocolFlags(can_add_recipients_with_esmtp_args=True),
            0x00000080,  # SMFIF_ADDRCPT_PAR
            id="can_add_recipients_with_esmtp_args",
        ),
        pytest.param(
            RequestProtocolFlags(can_remove_recipients=True),
            0x00000008,  # SMFIF_DELRCPT
            id="can_remove_recipients",
        ),
        pytest.param(
            RequestProtocolFlags(can_change_headers=True),
            0x00000010,  # SMFIF_CHGHDRS
            id="can_change_headers",
        ),
        pytest.param(
            RequestProtocolFlags(can_quarantine=True),
            0x00000020,  # SMFIF_QUARANTINE
            id="can_quarantine",
        ),
        pytest.param(
            RequestProtocolFlags(can_change_mail_from=True),
            0x00000040,  # SMFIF_CHGFROM
            id="can_change_mail_from",
        ),
    ],
)
def test_request_protocol_flags_non_default_actions(
    request_obj: RequestProtocolFlags, flag_test: int
) -> None:
    _, af = request_obj.encode_to_flags_bitmask()
    assert af & flag_test
