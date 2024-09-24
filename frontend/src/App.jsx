import React, { useState, useEffect, useRef } from "react";

function OlafChatClient() {
  const [userFingerprint, setUserFingerprint] = useState("");
  const [userName, setUserName] = useState("");
  const [selectedRecipients, setSelectedRecipients] = useState(["global"]);
  const [clients, setClients] = useState([]);
  const [storedMessages, setStoredMessages] = useState([]);
  const [messageText, setMessageText] = useState("");
  const [isRecipientDropdownOpen, setIsRecipientDropdownOpen] = useState(false);

  const dropdownRef = useRef(null);

  // Fetch user fingerprint and name on component mount
  useEffect(() => {
    fetch("/get_fingerprint")
      .then((response) => response.json())
      .then((data) => {
        setUserFingerprint(data.fingerprint);
        setUserName(data.name);
      })
      .catch((error) => {
        console.error("Error getting fingerprint:", error);
      });
  }, []);

  // Function to refresh client list
  const refreshClients = () => {
    console.log("Refreshing clients...");

    // First, request the client list to refresh the known clients
    fetch("/request_client_list")
      .then(() => fetch("/get_clients"))
      .then((response) => response.json())
      .then((data) => {
        console.log("Received client data:", data);
        const newClients = data.clients;

        // Check if the client list has changed
        if (JSON.stringify(newClients) !== JSON.stringify(clients)) {
          setClients(newClients);
        }
      })
      .catch((error) => {
        console.error("Error fetching clients:", error);
      });
  };

  // Function to refresh messages
  const refreshMessages = () => {
    console.log("Refreshing messages...");
    fetch("/get_messages")
      .then((response) => response.json())
      .then((data) => {
        console.log("Received messages:", data);
        const newMessages = data.messages;

        // Update the message list only with new messages
        newMessages.forEach((message) => {
          if (
            !storedMessages.some(
              (m) =>
                m.sender === message.sender && m.message === message.message
            )
          ) {
            setStoredMessages((prevMessages) => [...prevMessages, message]);
          }
        });
      })
      .catch((error) => {
        console.error("Error refreshing messages:", error);
      });
  };

  // Set up automatic refresh every second
  useEffect(() => {
    // Initial refresh
    refreshClients();
    refreshMessages();

    const interval = setInterval(() => {
      refreshClients();
      refreshMessages();
    }, 1000);

    return () => clearInterval(interval);
  }, [clients, storedMessages]);

  // Handle recipient change
  const handleRecipientChange = (event) => {
    const value = event.target.value;
    if (event.target.checked) {
      // Add recipient
      setSelectedRecipients((prev) => [...prev, value]);
    } else {
      // Remove recipient
      setSelectedRecipients((prev) => prev.filter((item) => item !== value));
    }
  };

  // Handle sending message
  const handleSendMessage = () => {
    if (messageText.trim() === "") {
      return;
    }

    if (selectedRecipients.includes("global")) {
      // Send public message
      console.log("Sending public message:", messageText);
      fetch("/send_public_message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: messageText }),
      })
        .then((response) => response.json())
        .then((data) => {
          console.log("Public message sent response:", data);
        })
        .catch((error) => {
          console.error("Error sending public message:", error);
        });
    }

    const privateRecipients = selectedRecipients.filter((r) => r !== "global");

    if (privateRecipients.length > 0) {
      // Send private message to selected recipients
      console.log(
        "Sending private message:",
        messageText,
        "to recipients:",
        privateRecipients
      );
      fetch("/send_message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText,
          recipients: privateRecipients,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          console.log("Private message sent response:", data);
        })
        .catch((error) => {
          console.error("Error sending message:", error);
        });
    }

    // Clear the message input after sending
    setMessageText("");
  };

  // Handle click outside the dropdown to close it
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        isRecipientDropdownOpen &&
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target)
      ) {
        setIsRecipientDropdownOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isRecipientDropdownOpen]);

  return (
    <div className="bg-gray-900 text-gray-100 min-h-screen flex flex-col">
      <div className="container mx-auto px-4 py-8 flex flex-col flex-grow">
        <h1 className="text-3xl font-bold mb-4">OLAF Chat Client</h1>

        {/* Message pane */}
        <div className="flex-grow overflow-y-auto bg-gray-800 p-4 rounded-lg">
          {storedMessages.map((message, index) => (
            <div key={index} className="mb-2">
              <strong>{message.sender}:</strong> {message.message}
            </div>
          ))}
        </div>

        {/* Message input area */}
        <div className="mt-4">
          <div className="relative">
            <div className="flex items-center bg-gray-800 text-white rounded-full px-4 py-3">
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() =>
                    setIsRecipientDropdownOpen(!isRecipientDropdownOpen)
                  }
                  className="text-white bg-gray-700 hover:bg-gray-600 rounded-full px-3 py-1 focus:outline-none mr-4 flex items-center"
                >
                  Recipients
                  {isRecipientDropdownOpen ? (
                    <svg
                      className="w-4 h-4 ml-1 transform rotate-180"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 15l7-7 7 7"
                      />
                    </svg>
                  ) : (
                    <svg
                      className="w-4 h-4 ml-1"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  )}
                </button>
                {isRecipientDropdownOpen && (
                  <div className="absolute z-10 bg-gray-800 text-white mb-2 rounded shadow-lg left-0 bottom-full">
                    <div className="p-2 max-h-60 overflow-y-auto">
                      <label className="flex items-center mb-1">
                        <input
                          type="checkbox"
                          value="global"
                          checked={selectedRecipients.includes("global")}
                          onChange={handleRecipientChange}
                          className="form-checkbox h-4 w-4 text-indigo-600"
                        />
                        <span className="ml-2">Global Chat</span>
                      </label>
                      {clients
                        .filter(
                          (fingerprint) => fingerprint !== userFingerprint
                        )
                        .map((fingerprint) => (
                          <label
                            key={fingerprint}
                            className="flex items-center mb-1"
                          >
                            <input
                              type="checkbox"
                              value={fingerprint}
                              checked={selectedRecipients.includes(fingerprint)}
                              onChange={handleRecipientChange}
                              className="form-checkbox h-4 w-4 text-indigo-600"
                            />
                            <span className="ml-2">{fingerprint}</span>
                          </label>
                        ))}
                    </div>
                  </div>
                )}
              </div>
              <input
                type="text"
                placeholder="Type your message..."
                className="flex-grow bg-transparent focus:outline-none text-white"
                value={messageText}
                onChange={(e) => setMessageText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
              />
              <button
                className="text-white bg-blue-600 hover:bg-blue-500 rounded-full px-3 py-1 focus:outline-none ml-4"
                onClick={handleSendMessage}
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OlafChatClient;
