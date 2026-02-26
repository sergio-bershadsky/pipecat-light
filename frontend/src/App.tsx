import { ConsoleTemplate } from "@pipecat-ai/voice-ui-kit";
import "@pipecat-ai/voice-ui-kit/styles.css";

export default function App() {
  return (
    <ConsoleTemplate
      startBotParams={{
        endpoint: "/api/connect",
      }}
      transportType="daily"
      titleText="Pipecat Light"
      assistantLabelText="Anya"
      userLabelText="You"
      noUserVideo
      noBotVideo
      noScreenControl
      theme="dark"
    />
  );
}
