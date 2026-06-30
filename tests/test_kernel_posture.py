"""Tests for kernel firewall posture assessment."""

from __future__ import annotations

from unittest.mock import patch

from app.tools.pentest.kernel_posture import (
    assess_conntrack,
    assess_kernel_posture,
    assess_redirects,
    assess_rp_filter,
    assess_ufw,
    format_kernel_posture_markdown,
)


class TestKernelPosture:

    @patch("app.tools.pentest.kernel_posture.platform.system", return_value="Darwin")
    def test_rp_filter_macos_not_applicable(self, _sys):
        finding = assess_rp_filter()
        assert finding["status"] == "not_applicable"
        assert finding["category"] == "rp_filter"

    @patch("app.tools.pentest.kernel_posture.platform.system", return_value="Linux")
    @patch("app.tools.pentest.kernel_posture._read_sysctl", return_value=(True, "0"))
    def test_rp_filter_disabled_linux(self, _sysctl, _sys):
        finding = assess_rp_filter()
        assert finding["status"] == "disabled"
        assert finding["severity"] == "high"
        assert "remediation" in finding

    @patch("app.tools.pentest.kernel_posture.platform.system", return_value="Linux")
    @patch("app.tools.pentest.kernel_posture._read_sysctl", return_value=(True, "1"))
    def test_rp_filter_strict_linux(self, _sysctl, _sys):
        finding = assess_rp_filter()
        assert finding["status"] == "strict"
        assert finding["severity"] == "low"

    @patch("app.tools.pentest.kernel_posture.platform.system", return_value="Linux")
    @patch(
        "app.tools.pentest.kernel_posture._read_sysctl",
        side_effect=[
            (True, "1"),
            (True, "0"),
            (True, "0"),
        ],
    )
    def test_redirects_mixed(self, _sysctl, _sys):
        findings = assess_redirects()
        assert len(findings) == 3
        enabled = [f for f in findings if f["status"] == "enabled"]
        disabled = [f for f in findings if f["status"] == "disabled"]
        assert len(enabled) == 1
        assert len(disabled) == 2

    @patch("app.tools.pentest.kernel_posture.platform.system", return_value="Darwin")
    def test_conntrack_macos_info(self, _sys):
        findings = assess_conntrack()
        assert findings[0]["status"] == "not_applicable"

    @patch("app.tools.pentest.kernel_posture.platform.system", return_value="Linux")
    @patch("app.tools.pentest.kernel_posture._read_sysctl", return_value=(True, "16384"))
    @patch("app.tools.pentest.kernel_posture._read_proc_file", return_value=(True, "15000"))
    def test_conntrack_near_exhaustion(self, _proc, _sysctl, _sys):
        findings = assess_conntrack()
        assert findings[0]["status"] == "near_exhaustion"
        assert findings[0]["severity"] == "critical"

    @patch("app.tools.pentest.kernel_posture._run_cmd", return_value=(1, "", ""))
    def test_ufw_not_installed(self, _cmd):
        finding = assess_ufw()
        assert finding["status"] == "not_installed"

    @patch("app.tools.pentest.kernel_posture._run_cmd")
    def test_ufw_active(self, mock_cmd):
        mock_cmd.side_effect = [
            (0, "/usr/sbin/ufw", ""),
            (0, "Status: active\nLogging: on", ""),
        ]
        finding = assess_ufw()
        assert finding["status"] == "active"

    @patch("app.tools.pentest.kernel_posture.platform.system", return_value="Darwin")
    @patch("app.tools.pentest.kernel_posture.assess_rp_filter")
    @patch("app.tools.pentest.kernel_posture.assess_redirects", return_value=[])
    @patch("app.tools.pentest.kernel_posture.assess_conntrack", return_value=[])
    @patch("app.tools.pentest.kernel_posture.assess_ufw")
    @patch("app.tools.pentest.kernel_posture.assess_firewall_backend", return_value=[])
    def test_assess_kernel_posture_structure(
        self, _backend, ufw, _ct, _redir, rp, _sys,
    ):
        rp.return_value = {"severity": "medium", "remediation": "fix rp"}
        ufw.return_value = {"severity": "low"}
        report = assess_kernel_posture()
        assert "findings" in report
        assert report["risk_level"] in ("low", "medium", "high", "critical")
        assert "fix rp" in report["remediations"]
        md = format_kernel_posture_markdown(report)
        assert "Kernel firewall posture" in md
