"""<=64KiB synthetic crypto only, own toy keys; never reads root recipient key."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from tempfile import mkdtemp
import time
from types import ModuleType
from unittest.mock import patch

C = "5d4b5c7cb02ff3c365532e16faead233093faac9"
REPO = Path(__file__).resolve().parents[3]


def main():
    started = datetime.now(timezone.utc).isoformat()
    began = time.monotonic_ns()
    source = subprocess.check_output(["git", "show", C + ":tools/m0_stream_escrow.py"], cwd=REPO)
    assert sha256(source).hexdigest() == "e894ba1c5b7c6370744dad09b9cfd7b008b0cc0002807275deaf6f9bc2d4bc9f"
    m = ModuleType("immutable_5d4b_crypto_peer")
    m.__file__ = "/synthetic/review/tools/m0_stream_escrow.py"
    exec(compile(source, m.__file__, "exec"), m.__dict__)
    private = Path(mkdtemp(prefix="uta-m0-independent-toy-", dir="/workspace"))
    os.chmod(private, 0o700)
    observations = []

    def command(argv, label):
        with (private / (label + ".stdout")).open("xb") as stdout, (private / (label + ".stderr")).open("xb") as stderr:
            result = subprocess.run(argv, stdout=stdout, stderr=stderr, timeout=3)
        assert result.returncode == 0, label

    certificate, key = private / "own-toy-cert.pem", private / "own-toy-key.pem"
    command(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
             "-out", str(certificate), "-subj", "/CN=M0-INDEPENDENT-TOY", "-days", "1"], "own-keygen")
    os.chmod(key, 0o600)
    pub = subprocess.run(["openssl", "x509", "-in", str(certificate), "-pubkey", "-noout"], capture_output=True, check=True, timeout=3).stdout
    spki = subprocess.run(["openssl", "pkey", "-pubin", "-outform", "DER"], input=pub, capture_output=True, check=True, timeout=3).stdout
    binding = dict(format=1, source_commit=m.SOURCE, control_commit=C,
                   controller_sha256="b30dda17b8951f593a74dbf4cdf97ba6e23e88e25919cfbad27fdcc710e50daa",
                   run_id="24680", run_attempt="1", case="B", stream="driver.stdout",
                   recipient_spki_sha256=sha256(spki).hexdigest(), capture_complete=True)
    body = b"INDEPENDENT_SYNTHETIC_ONLY_NO_TRADING_DATA\n" * 3
    assert len(body) <= 65536
    raw = private / "synthetic-original.stdout"
    raw.write_bytes(body)
    correct = private / "correct-gcm.cms"
    encrypted = m.encrypt_closed_stream(raw, correct, certificate, binding)
    accepted = m.decrypt_authenticated(correct, certificate, key, private / "positive-quarantine", binding)
    assert accepted["bytes"] == len(body) and accepted["sha256"] == sha256(body).hexdigest()
    observations.append(dict(case="correct_GCM_OAEP_SHA256_roundtrip", expected="ACCEPT", observed="ACCEPT", red=False,
                             body_bytes=len(body), body_sha256=sha256(body).hexdigest()))

    container = private / "synthetic-container.bin"
    container.write_bytes(m.container_header(binding, len(body), sha256(body).hexdigest()) + body)
    variants = [
        ("CBC_unauthenticated_PKCS1v15", ["-aes-256-cbc"]),
        ("GCM_unapproved_OAEP_SHA1", ["-aes-256-gcm", "-keyopt", "rsa_padding_mode:oaep", "-keyopt", "rsa_oaep_md:sha1", "-keyopt", "rsa_mgf1_md:sha1"]),
    ]
    for name, options in variants:
        cipher = private / (name + ".cms")
        command(["openssl", "cms", "-encrypt", "-binary", "-outform", "DER", "-recip", str(certificate),
                 *options, "-in", str(container), "-out", str(cipher)], "produce-" + name)
        printed = subprocess.run(["openssl", "cms", "-cmsout", "-inform", "DER", "-in", str(cipher), "-print"], capture_output=True, check=True, timeout=3).stdout
        observed_protocol = {token.decode(): token in printed for token in (b"pkcs7-envelopedData", b"id-smime-ct-authEnvelopedData", b"aes-256-cbc", b"aes-256-gcm", b"rsaEncryption", b"rsaesOaep", b"sha1", b"sha256")}
        try:
            result = m.decrypt_authenticated(cipher, certificate, key, private / (name + "-quarantine"), binding)
            observations.append(dict(case=name, expected="REJECT_PROTOCOL", observed="ACCEPT", red=True,
                                     actual_protocol=observed_protocol, accepted_binding=result["binding_valid"],
                                     returned_authenticated_flag=result["authenticated_decrypt_exit_zero"],
                                     plaintext_body_hash_matches=result["sha256"] == sha256(body).hexdigest()))
        except m.EscrowError as error:
            observations.append(dict(case=name, expected="REJECT_PROTOCOL", observed="REJECT", red=False,
                                     actual_protocol=observed_protocol, error_code=str(error)))

    tampered = private / "bad-tag.cms"
    damaged = bytearray(correct.read_bytes()); damaged[-1] ^= 1; tampered.write_bytes(damaged)
    parse_calls = []

    def forbidden_parse(*args, **kwargs):
        parse_calls.append("parse-called-after-failed-tag")
        raise AssertionError("unauthenticated container parsed")

    with patch.object(m, "validate_decrypted_container", forbidden_parse):
        try:
            m.decrypt_authenticated(tampered, certificate, key, private / "failed-tag-quarantine", binding)
            raise AssertionError("tampered tag accepted")
        except m.EscrowError as error:
            assert str(error) == "authenticated_decrypt_failed_do_not_parse"
    assert parse_calls == []
    partial = private / "failed-tag-quarantine/unaccepted-container.bin"
    observations.append(dict(case="failed_tag_never_parsed", expected="REJECT_BEFORE_PARSE", observed="REJECT_BEFORE_PARSE", red=False,
                             unauthenticated_output_bytes=partial.stat().st_size, parse_calls=parse_calls,
                             failed_plaintext_contents_not_read=True))
    wrong_binding = dict(binding, run_id="24681")
    try:
        m.decrypt_authenticated(correct, certificate, key, private / "wrong-run-quarantine", wrong_binding)
        raise AssertionError("wrong run accepted")
    except m.EscrowError as error:
        assert str(error) == "container_binding_mismatch"
    observations.append(dict(case="wrong_run_rejected", expected="REJECT", observed="REJECT", red=False))
    result = dict(control_commit=C, escrow_module_sha256=sha256(source).hexdigest(), started_at_utc=started,
                  finished_at_utc=datetime.now(timezone.utc).isoformat(), elapsed_monotonic_ns=time.monotonic_ns() - began,
                  cpu_affinity=sorted(os.sched_getaffinity(0)), synthetic_plaintext_bytes=len(body),
                  private_fixture_directory=str(private), actual_root_key_read=False, all_private_keys_are_new_self_owned_toys=True,
                  original_fixture_files_retained=True, original_binaries_not_published=True,
                  cases=observations, red_count=sum(case["red"] for case in observations),
                  actual_SQL_native_M0_profile_Actions_marker_push=False, execution_authorized=False, production_approved=False)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["red_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
