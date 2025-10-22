(function executeRule(current) {
    gs.info(" [Webhook BR] Triggered for Incident: " + current.number);
  
    try {
      var r = new sn_ws.RESTMessageV2();
      r.setHttpMethod("post");
      r.setEndpoint("https://your-cloud-function-url-here");
      r.setRequestHeader("Content-Type", "application/json");
  
      var user = current.caller_id.getRefRecord();
      var caller_email = user.email + "";
  
      var payload = {
        number: current.number + "",
        short_description: current.short_description + "",
        description: current.description + "",
        urgency: current.urgency + "",
        impact: current.impact + "",
        created_on: current.sys_created_on + "",
        caller_email: caller_email
      };
  
      r.setRequestBody(JSON.stringify(payload));
      r.executeAsync();
      gs.info("[Webhook BR] Webhook sent.");
    } catch (e) {
      gs.error("[Webhook BR] Error sending webhook: " + e.message);
    }
  })(current);