import React, { useState, useEffect, useRef } from "react";
import { ToastContainer, toast, cssTransition } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

function OlafChatClient() {
  const [userFingerprint, setUserFingerprint] = useState("");
  const [userName, setUserName] = useState("");
  const [serverAddress, setServerAddress] = useState("");
  const [serverPort, setServerPort] = useState("");
  const [httpPort, setHttpPort] = useState("");
  const [selectedRecipients, setSelectedRecipients] = useState(["global"]);
  const [clients, setClients] = useState([]);
  const [storedMessages, setStoredMessages] = useState([]);
  const [messageText, setMessageText] = useState("");
  const [isRecipientDropdownOpen, setIsRecipientDropdownOpen] = useState(false);
  const [publicHost, setPublicHost] = useState("");
  const [isDarkMode, setIsDarkMode] = useState(true); // Added for dark mode

  const dropdownRef = useRef(null);
  const fileInputRef = useRef(null);
  const messagePaneRef = useRef(null);

  // Fetch user preference for dark mode from localStorage
  useEffect(() => {
    const storedMode = localStorage.getItem("isDarkMode");
    if (storedMode !== null) {
      setIsDarkMode(storedMode === "true");
    }
  }, []);

  // Update localStorage when isDarkMode changes
  useEffect(() => {
    localStorage.setItem("isDarkMode", isDarkMode);
  }, [isDarkMode]);

  // Fetch user fingerprint, name, and server info on component mount
  useEffect(() => {
    fetch("/get_fingerprint")
      .then((response) => response.json())
      .then((data) => {
        setUserFingerprint(data.fingerprint);
        setUserName(data.name);
        setServerAddress(data.server_address);
        setServerPort(data.server_port);
        setHttpPort(data.http_port);
        setPublicHost(data.public_host);
      })
      .catch((error) => {
        console.error("Error getting fingerprint:", error);
        toast.error("Error getting user information.");
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
        toast.error("Error fetching client list.");
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

        // Replace storedMessages with newMessages to prevent duplicates
        setStoredMessages(newMessages);
      })
      .catch((error) => {
        console.error("Error refreshing messages:", error);
        toast.error("Error refreshing messages.");
      });
  };

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagePaneRef.current) {
      messagePaneRef.current.scrollTop = messagePaneRef.current.scrollHeight;
    }
  }, [storedMessages]);

  // Set up automatic refresh for messages every 5 seconds
  useEffect(() => {
    // Initial refresh
    refreshClients(); // Fetch clients on mount
    refreshMessages();

    const interval = setInterval(() => {
      refreshMessages();
    }, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, []);

  // Fetch clients when recipient dropdown is opened
  useEffect(() => {
    if (isRecipientDropdownOpen) {
      refreshClients();
    }
  }, [isRecipientDropdownOpen]);

  // Handle recipient change
  const handleRecipientChange = (event) => {
    const value = event.target.value;
    if (value === "global") {
      if (event.target.checked) {
        // 'global' is selected, unselect all other recipients
        setSelectedRecipients(["global"]);
      } else {
        // 'global' is unselected
        setSelectedRecipients([]);
      }
    } else {
      if (event.target.checked) {
        // Add recipient, ensure 'global' is not selected
        setSelectedRecipients((prev) => {
          const newRecipients = prev.filter((item) => item !== "global");
          return [...newRecipients, value];
        });
      } else {
        // Remove recipient
        setSelectedRecipients((prev) => prev.filter((item) => item !== value));
      }
    }
  };

  // Handle sending message
  const handleSendMessage = () => {
    if (messageText.trim() === "") {
      return;
    }

    if (selectedRecipients.length === 0) {
      toast.error("Please select at least one recipient.");
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
        .then((response) => {
          if (!response.ok) {
            throw new Error("Failed to send public message");
          }
          return response.json();
        })
        .then((data) => {
          console.log("Public message sent response:", data);
          // Fetch messages immediately after sending
          refreshMessages();
          // Show success toast
          toast.success("Public message sent successfully!");
        })
        .catch((error) => {
          console.error("Error sending public message:", error);
          toast.error("Failed to send public message.");
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
        .then((response) => {
          if (!response.ok) {
            throw new Error("Failed to send private message");
          }
          return response.json();
        })
        .then((data) => {
          console.log("Private message sent response:", data);
          // Fetch messages immediately after sending
          refreshMessages();
          // Show success toast
          toast.success("Private message sent successfully!");
        })
        .catch((error) => {
          console.error("Error sending message:", error);
          toast.error("Failed to send private message.");
        });
    }

    // Clear the message input after sending
    setMessageText("");
  };

  // Function to trigger file input click
  const triggerFileUpload = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  // Function to handle file selection
  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (selectedRecipients.length === 0) {
        toast.error("Please select at least one recipient.");
        return;
      }

      const formData = new FormData();
      formData.append("file", file);

      // Include selected recipients
      selectedRecipients.forEach((recipient) => {
        formData.append("recipients[]", recipient);
      });

      fetch("/upload_file", {
        method: "POST",
        body: formData,
      })
        .then(async (response) => {
          if (response.ok) {
            const data = await response.json();
            console.log("File upload response:", data);
            // Fetch messages immediately after sending
            refreshMessages();
            // Show success toast
            toast.success("File uploaded successfully!");
          } else {
            // Handle errors
            const errorData = await response.json();
            console.error("File upload error:", errorData);
            toast.error(errorData.error || "File upload failed");
          }
          // Clear selected file after upload
          event.target.value = null;
        })
        .catch((error) => {
          console.error("Error uploading file:", error);
          toast.error("Error uploading file");
        });
    }
  };

  // Function to get file type icon
  const getFileTypeIcon = (fileUrl) => {
    const extension = fileUrl.split(".").pop().toLowerCase();
    switch (extension) {
      case "jpg":
      case "jpeg":
      case "png":
      case "gif":
      case "bmp":
      case "tiff":
      case "svg":
      case "webp":
        return "🖼️"; // Image icon
      case "mp3":
      case "wav":
      case "ogg":
      case "flac":
      case "aac":
      case "m4a":
        return "🎵"; // Audio file icon
      case "mp4":
      case "mov":
      case "avi":
      case "mkv":
      case "webm":
      case "wmv":
        return "🎥"; // Video file icon
      case "pdf":
        return "📄"; // PDF icon
      case "zip":
      case "rar":
      case "7z":
      case "tar":
      case "gz":
        return "🗜️"; // Archive icon
      case "txt":
      case "rtf":
      case "md":
        return "📝"; // Text document icon
      case "doc":
      case "docx":
      case "odt":
        return "📄"; // Word document icon
      case "xls":
      case "xlsx":
      case "ods":
        return "📊"; // Spreadsheet icon
      case "ppt":
      case "pptx":
      case "odp":
        return "📈"; // Presentation icon
      case "html":
      case "css":
      case "js":
      case "jsx":
      case "ts":
      case "tsx":
      case "json":
      case "xml":
      case "yml":
      case "yaml":
        return "🌐"; // Code file icon
      case "exe":
      case "msi":
      case "apk":
        return "💾"; // Executable file icon
      default:
        return "📁"; // Default file icon
    }
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

  // Sort messages by timestamp
  const sortedMessages = [...storedMessages].sort(
    (a, b) => a.timestamp - b.timestamp
  );

  // Define custom toast classes
  const toastClasses = {
    container: `toast-container ${isDarkMode ? "dark" : "light"}`,
    body: "toast-body",
    progress: "toast-progress",
  };

  // Transition for toasts
  const Slide = cssTransition({
    enter: "slideIn",
    exit: "slideOut",
    duration: 300,
  });

  return (
    <div className={`${isDarkMode ? "dark" : ""}`}>
      <div className="bg-gray-100 text-gray-900 min-h-screen flex flex-col dark:bg-gray-900 dark:text-gray-100">
        <ToastContainer
          position="top-right"
          autoClose={5000}
          hideProgressBar={false}
          newestOnTop={false}
          closeOnClick
          rtl={false}
          pauseOnFocusLoss
          draggable
          pauseOnHover
          transition={Slide}
          toastClassName={() =>
            `relative flex p-3 min-h-10 rounded-md justify-between overflow-hidden cursor-pointer mb-2 bg-white text-gray-800 dark:bg-gray-800 dark:text-white`
          }
          bodyClassName={() => "text-sm flex items-center"}
          progressClassName="bg-blue-500"
        />
        <div className="container mx-auto px-4 py-8 flex flex-col flex-grow">
          {/* Header section */}
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-3xl font-bold">OMesh</h1>
            {/* Dark Mode Toggle */}
            <div className="flex items-center">
              <label className="flex items-center cursor-pointer">
                <div className="relative">
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={isDarkMode}
                    onChange={() => setIsDarkMode(!isDarkMode)}
                  />
                  <div
                    className={`block w-14 h-8 rounded-full ${
                      isDarkMode ? "bg-blue-600" : "bg-gray-300"
                    }`}
                  ></div>
                  <div
                    className={`dot absolute left-1 top-1 w-6 h-6 rounded-full transition ${
                      isDarkMode
                        ? "transform translate-x-6 bg-white"
                        : "bg-white"
                    }`}
                  ></div>
                </div>
                <span className="ml-3 text-sm font-medium">
                  {isDarkMode ? "Dark" : "Light"}
                </span>
              </label>
            </div>
          </div>

          {/* Client info */}
          <div className="mb-4">
            <p>
              <strong>Name:</strong> {userName}
            </p>
            <p>
              <strong>Fingerprint:</strong> {userFingerprint}
            </p>
            <p>
              <strong>Connected to:</strong> {serverAddress}:{serverPort}
            </p>
            <p>
              <strong>File Server:</strong>{" "}
              <a
                href={`http://${publicHost}:${httpPort}/files`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:underline"
              >
                http://{publicHost}:{httpPort}/files
              </a>
            </p>
          </div>

          {/* Message pane */}
          <div
            className="flex-grow overflow-y-auto bg-gray-200 p-4 rounded-lg dark:bg-gray-800"
            ref={messagePaneRef}
          >
            {/* Display selected recipients */}
            <div className="mb-4">
              <strong>Chatting with:</strong> {selectedRecipients.join(", ")}
            </div>

            {sortedMessages.map((message, index) => {
              const isOwnMessage = message.sender === userFingerprint;
              const isFileMessage = message.message.startsWith("[File]");
              let messageContent = message.message;
              if (isFileMessage) {
                messageContent = message.message.replace("[File]", "").trim();
              }

              // Format timestamp
              const formattedTime = new Date(
                message.timestamp * 1000
              ).toLocaleString();

              return (
                <div
                  key={index}
                  className={`mb-4 flex ${
                    isOwnMessage ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`p-2 rounded-lg ${
                      isOwnMessage
                        ? "bg-green-600 text-white dark:bg-green-500"
                        : "bg-gray-300 text-gray-900 dark:bg-gray-700 dark:text-white"
                    }`}
                  >
                    <div className="flex items-center mb-1">
                      <strong className="mr-2 break-all">
                        {isOwnMessage ? "You" : message.sender}
                      </strong>
                      <span
                        className={`text-sm ${
                          isOwnMessage
                            ? "text-white-500 dark:text-white-300"
                            : "text-gray-500 dark:text-gray-300"
                        }`}
                      >
                        {formattedTime}
                      </span>
                    </div>
                    <div>
                      {isFileMessage ? (
                        <div className="mt-2">
                          {["jpg", "jpeg", "png", "gif", "webp"].includes(
                            messageContent.split(".").pop().toLowerCase()
                          ) ? (
                            <img
                              src={messageContent}
                              alt="Shared file"
                              className="max-w-full max-h-48 rounded-lg"
                            />
                          ) : (
                            <div className="flex items-center">
                              <span className="mr-2">
                                {getFileTypeIcon(messageContent)}
                              </span>
                              <a
                                href={messageContent}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="underline"
                              >
                                {messageContent.split("/").pop()}
                              </a>
                            </div>
                          )}
                          <div className="mt-2">
                            <span
                              className={`text-sm ${
                                isOwnMessage
                                  ? "text-white-500 dark:text-white-300"
                                  : "text-gray-500 dark:text-gray-300"
                              }`}
                            >
                              View at:{" "}
                            </span>
                            <a
                              href={messageContent}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline break-all"
                            >
                              {messageContent}
                            </a>
                          </div>
                        </div>
                      ) : (
                        <p className="break-words">{messageContent}</p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Message input area */}
          <div className="mt-4">
            <div className="relative">
              <div className="flex items-center bg-gray-200 text-gray-900 rounded-full px-4 py-3 dark:bg-gray-800 dark:text-white">
                {/* File upload button */}
                <button
                  onClick={triggerFileUpload}
                  className="text-gray-900 hover:bg-gray-300 rounded-full px-2 py-1 focus:outline-none mr-2 flex items-center dark:text-white dark:hover:bg-gray-700"
                >
                  <svg
                    className="w-6 h-6"
                    fill="currentColor"
                    stroke="none"
                    viewBox="0 0 20 20"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" />
                  </svg>
                </button>
                {/* Hidden file input */}
                <input
                  type="file"
                  onChange={handleFileChange}
                  ref={fileInputRef}
                  style={{ display: "none" }}
                />
                <div className="relative" ref={dropdownRef}>
                  {/* Recipient dropdown button */}
                  <button
                    onClick={() =>
                      setIsRecipientDropdownOpen(!isRecipientDropdownOpen)
                    }
                    className="text-gray-900 bg-gray-300 hover:bg-gray-400 rounded-full px-3 py-1 focus:outline-none mr-4 flex items-center dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
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
                    <div
                      className="absolute z-10 bg-blue-300 text-gray-900 mb-2 rounded shadow-lg left-0 bottom-full min-w-max dark:bg-blue-700 dark:text-white"
                      style={{ whiteSpace: "nowrap" }}
                    >
                      <div className="p-2 max-h-60 overflow-y-auto">
                        <label className="flex items-center mb-1">
                          <input
                            type="checkbox"
                            value="global"
                            checked={selectedRecipients.includes("global")}
                            onChange={handleRecipientChange}
                            className="form-checkbox h-4 w-4 text-indigo-600"
                          />
                          <span className="ml-2 whitespace-nowrap">
                            Global Chat
                          </span>
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
                                checked={selectedRecipients.includes(
                                  fingerprint
                                )}
                                onChange={handleRecipientChange}
                                className="form-checkbox h-4 w-4 text-indigo-600"
                              />
                              <span className="ml-2 whitespace-nowrap">
                                {fingerprint}
                              </span>
                            </label>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
                <input
                  type="text"
                  placeholder="Type your message..."
                  className="flex-grow bg-transparent focus:outline-none text-gray-900 dark:text-white"
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
                  className={`text-white rounded-full px-3 py-1 focus:outline-none ml-4 ${
                    isDarkMode
                      ? "bg-blue-500 hover:bg-blue-600"
                      : "bg-gray-600 hover:bg-gray-700"
                  }`}
                  onClick={handleSendMessage}
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Footer section */}
        <footer className="text-gray-600 py-4 text-center dark:text-gray-400">
          <span className="text-sm">
            An open source implementation of OLAF's Neighbourhood protocol,
            developed in Python and React.
          </span>
          <a
            href="https://github.com/santiagosayshey/OMesh"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center ml-2 text-gray-600 hover:text-blue-500 dark:text-gray-400 dark:hover:text-blue-300"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-4 h-4 ml-1"
              fill="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
              role="img"
              focusable="false"
            >
              <title>GitHub Repository</title>
              <path
                fillRule="evenodd"
                d="M12 0C5.372 0 0 5.373 0 12c0 5.303 3.438 9.8 8.205 11.387.6.113.82-.258.82-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.73.083-.73 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.809 1.305 3.495.998.108-.776.418-1.305.762-1.605-2.665-.305-5.467-1.332-5.467-5.93 0-1.31.468-2.381 1.235-3.221-.123-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.3 1.23a11.52 11.52 0 013.003-.404c1.02.005 2.045.138 3.003.404 2.29-1.552 3.297-1.23 3.297-1.23.653 1.653.241 2.874.119 3.176.77.84 1.233 1.911 1.233 3.221 0 4.61-2.807 5.625-5.48 5.92.43.372.823 1.102.823 2.222v3.293c0 .322.218.694.825.576C20.565 21.796 24 17.3 24 12c0-6.627-5.373-12-12-12z"
                clipRule="evenodd"
              />
            </svg>
          </a>
        </footer>
      </div>
    </div>
  );
}

export default OlafChatClient;
