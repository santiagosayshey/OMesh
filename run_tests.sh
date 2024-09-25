#!/bin/bash

# run_tests.sh
# This script runs cryptographic function tests and provides a detailed summary.

# Color codes for output formatting
RED='\033[0;31m'     # Red for failures
GREEN='\033[0;32m'   # Green for successes
YELLOW='\033[1;33m'  # Yellow for test titles
NC='\033[0m'         # No Color

echo -e "\n========================================"
echo -e "   Cryptographic Function Testing"
echo -e "========================================\n"

declare -a tests=(
    "test_key_generation.py:Generating Secure Keys:Checks if the system can create secure keys for encryption.:The system generates a key with a modulus length of 2048 bits and a public exponent of 65537."
    "test_asymmetric_encryption.py:Encrypting and Decrypting Messages:Verifies that messages can be locked and unlocked properly.:The decrypted message matches the original message."
    "test_digital_signature.py:Signing Messages:Ensures messages can be signed to confirm the sender's identity.:Signature verification succeeds with the correct key and fails with an incorrect key."
    "test_symmetric_encryption.py:Fast Message Encryption:Confirms that messages can be quickly encrypted and decrypted.:The decrypted message matches the original message."
    "test_fingerprint_calculation.py:Creating Unique IDs for Users:Checks that each user gets a unique identifier.:The fingerprint matches the SHA-256 hash of the public key."
    "test_counter_mechanism.py:Preventing Replay Attacks:Verifies that old messages cannot be resent to trick users.:Messages with increasing counters are accepted; messages with same or lower counters are rejected."
    "test_message_structure.py:Message Structure Compliance Testing:Verifies that all messages adhere to the protocol's data structures and field requirements.:Messages match the expected structures; mismatches are reported with actual output."
)

# Function to run a test and print the result
run_test() {
    IFS=":" read -r script_name test_title test_desc expected_outcome <<< "$1"

    echo -e "----------------------------------------"
    echo -e "${YELLOW}Test: ${test_title}${NC}"
    echo -e "${YELLOW}Description:${NC} ${test_desc}"
    echo -e "${YELLOW}Expected Outcome:${NC} ${expected_outcome}"

    # Run the test script and capture output
    test_output=$(python3 -m unittest tests/"$script_name" 2>&1)
    result=$?

    if [ $result -eq 0 ]; then
        # Extract actual results from test output
        actual_result=$(echo "$test_output" | grep -E "^Actual Result:.*" | sed 's/Actual Result: //')
        if [ -z "$actual_result" ]; then
            actual_result="All tests passed."
        fi
        echo -e "${GREEN}Actual Result:${NC} $actual_result"
        echo -e "${GREEN}Status:${NC} ${GREEN}PASS${NC}\n"
    else
        echo -e "${RED}Actual Result:${NC} Test failed."
        echo -e "${RED}Details:${NC}\n$test_output"
        echo -e "${RED}Status:${NC} ${RED}FAIL${NC}\n"
    fi
}

# Loop through all tests
for test_info in "${tests[@]}"; do
    run_test "$test_info"
done

echo -e "========================================"
echo -e "   Testing Complete"
echo -e "========================================\n"
