"""
Test script for M-Pesa callback server.

This script simulates M-Pesa callbacks to test the callback server functionality.
"""

import requests
import json
from datetime import datetime
import time

# Callback server URL
BASE_URL = "http://localhost:8000"
CALLBACK_URL = f"{BASE_URL}/mpesa/callback"


def test_health_check():
    """Test the health check endpoint."""
    print("\n" + "="*60)
    print("Testing Health Check Endpoint")
    print("="*60)

    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print("❌ Health check failed")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_root_endpoint():
    """Test the root endpoint."""
    print("\n" + "="*60)
    print("Testing Root Endpoint")
    print("="*60)

    try:
        response = requests.get(BASE_URL)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Root endpoint working")
            return True
        else:
            print("❌ Root endpoint failed")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_successful_callback():
    """Test a successful M-Pesa callback."""
    print("\n" + "="*60)
    print("Testing Successful Payment Callback")
    print("="*60)

    # Current timestamp in M-Pesa format (YYYYMMDDHHmmss)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "29115-34620561-1",
                "CheckoutRequestID": f"ws_CO_{timestamp}",
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {
                            "Name": "Amount",
                            "Value": 1000.00
                        },
                        {
                            "Name": "MpesaReceiptNumber",
                            "Value": f"TEST{timestamp[:8]}"
                        },
                        {
                            "Name": "Balance"
                        },
                        {
                            "Name": "TransactionDate",
                            "Value": int(timestamp)
                        },
                        {
                            "Name": "PhoneNumber",
                            "Value": 254708374149
                        }
                    ]
                }
            }
        }
    }

    print(f"\nSending payload:")
    print(json.dumps(payload, indent=2))

    try:
        response = requests.post(
            CALLBACK_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Successful callback processed")
            return True
        else:
            print("❌ Callback processing failed")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_failed_callback():
    """Test a failed M-Pesa callback."""
    print("\n" + "="*60)
    print("Testing Failed Payment Callback")
    print("="*60)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "29115-34620561-2",
                "CheckoutRequestID": f"ws_CO_FAILED_{timestamp}",
                "ResultCode": 1032,
                "ResultDesc": "Request cancelled by user",
                "CallbackMetadata": None
            }
        }
    }

    print(f"\nSending payload:")
    print(json.dumps(payload, indent=2))

    try:
        response = requests.post(
            CALLBACK_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Failed callback processed")
            return True
        else:
            print("❌ Callback processing failed")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_invalid_callback():
    """Test an invalid callback structure."""
    print("\n" + "="*60)
    print("Testing Invalid Callback Structure")
    print("="*60)

    # Missing required fields
    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "test-invalid"
                # Missing required fields
            }
        }
    }

    print(f"\nSending invalid payload:")
    print(json.dumps(payload, indent=2))

    try:
        response = requests.post(
            CALLBACK_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 400:
            print("✅ Invalid callback rejected correctly")
            return True
        else:
            print("❌ Invalid callback not handled properly")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_timeout_callback():
    """Test a timeout callback."""
    print("\n" + "="*60)
    print("Testing Timeout Callback")
    print("="*60)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "29115-34620561-3",
                "CheckoutRequestID": f"ws_CO_TIMEOUT_{timestamp}",
                "ResultCode": 1,
                "ResultDesc": "The balance is insufficient for the transaction",
                "CallbackMetadata": None
            }
        }
    }

    print(f"\nSending payload:")
    print(json.dumps(payload, indent=2))

    try:
        response = requests.post(
            CALLBACK_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Timeout callback processed")
            return True
        else:
            print("❌ Callback processing failed")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def run_all_tests():
    """Run all callback tests."""
    print("\n" + "="*60)
    print("M-PESA CALLBACK SERVER TEST SUITE")
    print("="*60)
    print(f"Target URL: {BASE_URL}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    tests = [
        ("Health Check", test_health_check),
        ("Root Endpoint", test_root_endpoint),
        ("Successful Payment", test_successful_callback),
        ("Failed Payment", test_failed_callback),
        ("Invalid Structure", test_invalid_callback),
        ("Timeout/Insufficient Balance", test_timeout_callback),
    ]

    results = []

    for test_name, test_func in tests:
        time.sleep(1)  # Brief pause between tests
        result = test_func()
        results.append((test_name, result))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "-"*60)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {total - passed} test(s) failed")

    print("="*60)


if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
