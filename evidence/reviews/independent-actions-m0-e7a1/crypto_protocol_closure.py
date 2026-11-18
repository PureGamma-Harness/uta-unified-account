"""Minimal strict-profile closure with original toy ciphers, <=64KiB, CPU3."""
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

C = "e7a1b3ee22a957350359463da60b99d9df6c589a"
REPO = Path(__file__).resolve().parents[3]


def main():
    started = datetime.now(timezone.utc).isoformat(); began = time.monotonic_ns()
    source = subprocess.check_output(["git", "show", C + ":tools/m0_stream_escrow.py"], cwd=REPO)
    assert sha256(source).hexdigest() == "89f48b50d22a1b8c5898ed9413ad6bc2567f6cd30c0a58626d0921f5e91ec83e"
    previous = json.loads(subprocess.check_output(["git", "show", "c617134f648bf4a79af2742e87fd96073d232428:evidence/reviews/independent-actions-m0-5d4b/crypto-first.stdout.json"], cwd=REPO))
    preserved = json.loads(subprocess.check_output(["git", "show", "c617134f648bf4a79af2742e87fd96073d232428:evidence/reviews/independent-actions-m0-5d4b/private-toy-retention-manifest.json"], cwd=REPO))
    old = Path(previous["private_fixture_directory"])
    assert old == Path(preserved["private_fixture_directory"]) and old.parent == Path("/workspace") and old.name.startswith("uta-m0-independent-toy-")
    files = {item["path"]: item for item in preserved["files"]}
    for name in ["own-toy-key.pem", "own-toy-cert.pem", "synthetic-original.stdout", "CBC_unauthenticated_PKCS1v15.cms", "GCM_unapproved_OAEP_SHA1.cms"]:
        assert sha256((old / name).read_bytes()).hexdigest() == files[name]["sha256"]
    key, certificate = old / "own-toy-key.pem", old / "own-toy-cert.pem"
    private = Path(mkdtemp(prefix="uta-m0-independent-der-", dir="/workspace")); os.chmod(private, 0o700)
    m = ModuleType("fixed_e7_strict_crypto_review"); m.__file__ = "/synthetic/control/tools/m0_stream_escrow.py"
    exec(compile(source, m.__file__, "exec"), m.__dict__)
    pub = subprocess.run(["openssl", "x509", "-in", str(certificate), "-pubkey", "-noout"], capture_output=True, check=True, timeout=3).stdout
    spki = subprocess.run(["openssl", "pkey", "-pubin", "-outform", "DER"], input=pub, capture_output=True, check=True, timeout=3).stdout
    old_binding = dict(format=1, source_commit=m.SOURCE, control_commit="5d4b5c7cb02ff3c365532e16faead233093faac9",
                       controller_sha256="b30dda17b8951f593a74dbf4cdf97ba6e23e88e25919cfbad27fdcc710e50daa",
                       run_id="24680", run_attempt="1", case="B", stream="driver.stdout",
                       recipient_spki_sha256=sha256(spki).hexdigest(), capture_complete=True)
    observations = []
    for name in ["CBC_unauthenticated_PKCS1v15", "GCM_unapproved_OAEP_SHA1"]:
        quarantine = private / (name + "-must-not-exist")
        calls = []

        def forbidden(*args, **kwargs):
            calls.append("decrypt-or-parse-called")
            raise AssertionError("protocol must reject before decrypt/parse")

        with patch.object(m.subprocess, "run", forbidden), patch.object(m, "validate_decrypted_container", forbidden):
            try:
                m.decrypt_authenticated(old / (name + ".cms"), certificate, key, quarantine, old_binding)
                raise AssertionError("original protocol counterexample still accepted")
            except m.EscrowError as error:
                code = str(error)
        assert calls == [] and not quarantine.exists()
        observations.append(dict(case=name, observed="REJECT_BEFORE_DECRYPT", original_cipher_sha256=files[name + ".cms"]["sha256"],
                                 original_cipher_bytes_unchanged=True, quarantine_created=False, decrypt_or_parse_calls=calls, error_code=code))
    binding = dict(old_binding, control_commit=C, controller_sha256="6c5656dc45a8648aff8e309f2d082f9d3e4af5f456acaeeaed4d5be447a176af")
    body = (old / "synthetic-original.stdout").read_bytes(); assert len(body) == 129 and len(body) <= 65536
    raw = private / "own-synthetic.stdout"; raw.write_bytes(body)
    correct = private / "new-correct-gcm.cms"
    m.encrypt_closed_stream(raw, correct, certificate, binding)
    protocol = m.validate_cms_protocol(correct)
    accepted = m.decrypt_authenticated(correct, certificate, key, private / "positive-quarantine", binding)
    assert accepted["bytes"] == len(body) and accepted["sha256"] == sha256(body).hexdigest()
    observations.append(dict(case="new_exact_protocol_positive", observed="ACCEPT", protocol=protocol,
                             original_bytes_verified=True, synthetic_bytes=len(body)))
    container = private / "synthetic-container.bin"; container.write_bytes(m.container_header(binding, len(body), sha256(body).hexdigest()) + body)
    bad_mgf = private / "gcm-mgf1-sha1.cms"
    with (private / "mgf1-produce.stdout").open("xb") as stdout, (private / "mgf1-produce.stderr").open("xb") as stderr:
        generated = subprocess.run(["openssl", "cms", "-encrypt", "-binary", "-outform", "DER", "-aes-256-gcm", "-recip", str(certificate),
                                    "-keyopt", "rsa_padding_mode:oaep", "-keyopt", "rsa_oaep_md:sha256", "-keyopt", "rsa_mgf1_md:sha1",
                                    "-in", str(container), "-out", str(bad_mgf)], stdout=stdout, stderr=stderr, timeout=3)
    assert generated.returncode == 0
    try: m.validate_cms_protocol(bad_mgf); raise AssertionError("MGF1-SHA1 accepted")
    except m.EscrowError as error: observations.append(dict(case="MGF1_SHA1", observed="REJECT", error_code=str(error)))
    cipher = correct.read_bytes(); count = cipher[1] & 127
    assert cipher[0] == 0x30 and cipher[1] & 128 and 1 <= count <= 4
    bad_oid = bytearray(m.OID_AUTH); bad_oid[-1] ^= 1
    canaries = {"trailing": cipher + b"\0", "truncated": cipher[:-1], "indefinite": b"\x30\x80" + cipher[2:],
                "nonminimal_length": bytes([0x30, 0x80 | (count + 1), 0]) + cipher[2:],
                "wrong_content_OID": cipher.replace(m.OID_AUTH, bytes(bad_oid), 1)}
    for name, data in canaries.items():
        path = private / (name + ".cms"); path.write_bytes(data)
        try: m.validate_cms_protocol(path); raise AssertionError("DER canary accepted: " + name)
        except m.EscrowError as error: observations.append(dict(case="DER_" + name, observed="REJECT", error_code=str(error)))
    bad_tag = bytearray(cipher); bad_tag[-1] ^= 1
    path = private / "tag-failed.cms"; path.write_bytes(bad_tag)
    assert m.validate_cms_protocol(path)["protocol_verified"] is True
    parse_calls = []

    def no_parse(*args, **kwargs):
        parse_calls.append("unauthenticated-parse")
        raise AssertionError("failed tag must not parse")

    with patch.object(m, "validate_decrypted_container", no_parse):
        try: m.decrypt_authenticated(path, certificate, key, private / "failed-tag-quarantine", binding); raise AssertionError("tag accepted")
        except m.EscrowError as error: assert str(error) == "authenticated_decrypt_failed_do_not_parse"
    assert parse_calls == []
    observations.append(dict(case="failed_tag_no_parse", observed="REJECT", protocol_is_not_authentication=True,
                             unauthenticated_output_bytes=(private / "failed-tag-quarantine/unaccepted-container.bin").stat().st_size,
                             failed_plaintext_contents_not_read=True, parse_calls=parse_calls))
    try: m.decrypt_authenticated(correct, certificate, key, private / "wrong-run-quarantine", dict(binding, run_id="24681")); raise AssertionError("wrong run accepted")
    except m.EscrowError as error: assert str(error) == "container_binding_mismatch"
    observations.append(dict(case="wrong_run", observed="REJECT"))
    result = dict(control_commit=C, escrow_module_sha256=sha256(source).hexdigest(), started_at_utc=started,
                  finished_at_utc=datetime.now(timezone.utc).isoformat(), elapsed_monotonic_ns=time.monotonic_ns() - began,
                  CPU_affinity=sorted(os.sched_getaffinity(0)), original_CBC_and_OAEP1_cipher_bytes_reused=True,
                  private_fixture_directory=str(private), previous_self_owned_toy_directory=str(old), synthetic_plaintext_bytes=len(body),
                  actual_root_key_read=False, old_unaccepted_plaintexts_read=False, private_keys_copied=False,
                  cases=observations, red_count=0, actual_SQL_native_M0_Actions_marker_push=False,
                  execution_authorized=False, production_approved=False)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__": main()
