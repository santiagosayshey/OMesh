import React, { useState, useEffect } from "react";

function OlafChatClient() {
  const [userFingerprint, setUserFingerprint] = useState("");
  const [userName, setUserName] = useState("");
  const [selectedRecipient, setSelectedRecipient] = useState("global");
  const [clients, setClients] = useState([]);
  const [storedMessages, setStoredMessages] = useState([]);
  const [messageText, setMessageText] = useState("");

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

  // Handle sending message
  const handleSendMessage = () => {
    const recipient = selectedRecipient;

    if (recipient === "global") {
      console.log("Sending public message:", messageText);
      fetch("/send_public_message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: messageText }),
      })
        .then((response) => response.json())
        .then((data) => {
          console.log("Public message sent response:", data);
          alert(data.status);
        })
        .catch((error) => {
          console.error("Error sending public message:", error);
        });
    } else {
      console.log(
        "Sending private message:",
        messageText,
        "to recipient:",
        recipient
      );
      fetch("/send_message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText,
          recipients: [recipient],
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          console.log("Message sent response:", data);
          alert(data.status);
        })
        .catch((error) => {
          console.error("Error sending message:", error);
        });
    }

    // Clear the message input after sending
    setMessageText("");
  };

  return (
    <div className="bg-dark-100 text-gray-100 min-h-screen">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8">OLAF Chat Client</h1>

        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-2">Your Fingerprint</h2>
          <p className="bg-dark-200 p-2 rounded">
            {userFingerprint
              ? `${userFingerprint} (${userName})`
              : "Loading..."}
          </p>
        </div>

        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-2">Recipients</h2>
          <div className="bg-dark-200 p-4 rounded max-h-60 overflow-y-auto">
            <div className="mb-2">
              <input
                type="radio"
                id="global"
                name="recipient"
                value="global"
                className="hidden peer"
                checked={selectedRecipient === "global"}
                onChange={() => setSelectedRecipient("global")}
              />
              <label
                htmlFor="global"
                className={`inline-block w-full p-2 text-gray-200 bg-dark-300 rounded-lg cursor-pointer ${
                  selectedRecipient === "global"
                    ? "bg-indigo-600 text-white"
                    : "hover:bg-dark-400"
                }`}
              >
                Global Chat
              </label>
            </div>

            {clients
              .filter((fingerprint) => fingerprint !== userFingerprint)
              .map((fingerprint) => (
                <div className="mb-2" key={fingerprint}>
                  <input
                    type="radio"
                    id={fingerprint}
                    name="recipient"
                    value={fingerprint}
                    className="hidden peer"
                    checked={selectedRecipient === fingerprint}
                    onChange={() => setSelectedRecipient(fingerprint)}
                  />
                  <label
                    htmlFor={fingerprint}
                    className={`inline-block w-full p-2 text-gray-200 bg-dark-300 rounded-lg cursor-pointer ${
                      selectedRecipient === fingerprint
                        ? "bg-indigo-600 text-white"
                        : "hover:bg-dark-400"
                    }`}
                  >
                    {fingerprint}
                  </label>
                </div>
              ))}
          </div>
        </div>

        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-2">Send Message</h2>
          <textarea
            id="message-text"
            rows="4"
            className="w-full p-2 mb-2 bg-dark-200 text-gray-100 rounded"
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
          ></textarea>
          <button
            id="send-message"
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded"
            onClick={handleSendMessage}
          >
            Send Message
          </button>
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-2">Messages</h2>
          <ul id="message-list" className="bg-dark-200 p-2 rounded">
            {storedMessages.map((message, index) => (
              <li key={index}>
                <strong>{message.sender}:</strong> {message.message}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default OlafChatClient;
