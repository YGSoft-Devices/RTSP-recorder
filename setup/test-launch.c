/* 
 * test-launch - GStreamer RTSP Server with Basic/Digest Authentication
 * Version: 2.1.0
 * 
 * Environment variables:
 *   RTSP_PORT     - Port to listen on (default: 8554)
 *   RTSP_PATH     - Mount path (default: /stream)
 *   RTSP_USER     - Username for authentication (optional)
 *   RTSP_PASSWORD - Password for authentication (optional)
 *   RTSP_REALM    - Authentication realm (default: "RPi Camera")
 *   RTSP_AUTH_METHOD - "basic", "digest", or "both" (default: "both")
 *
 * If RTSP_USER and RTSP_PASSWORD are both set, authentication is required.
 * If either is empty/unset, the stream is accessible without authentication.
 * 
 * Most RTSP clients (including Synology Surveillance Station) prefer Digest auth.
 */
#include <gst/gst.h>
#include <gst/rtsp-server/rtsp-server.h>
#include <stdlib.h>
#include <string.h>

static gboolean
timeout_callback (GstRTSPServer * server)
{
  GstRTSPSessionPool *pool;
  pool = gst_rtsp_server_get_session_pool (server);
  gst_rtsp_session_pool_cleanup (pool);
  g_object_unref (pool);
  return TRUE;
}

int
main (int argc, char *argv[])
{
  GMainLoop *loop;
  GstRTSPServer *server;
  GstRTSPMountPoints *mounts;
  GstRTSPMediaFactory *factory;
  GstRTSPAuth *auth = NULL;
  GstRTSPToken *token;
  gchar *basic;
  gchar *str;
  
  /* Configuration from environment */
  const gchar *port = g_getenv ("RTSP_PORT");
  const gchar *path = g_getenv ("RTSP_PATH");
  const gchar *user = g_getenv ("RTSP_USER");
  const gchar *password = g_getenv ("RTSP_PASSWORD");
  const gchar *realm = g_getenv ("RTSP_REALM");
  const gchar *auth_method = g_getenv ("RTSP_AUTH_METHOD");
  
  /* Defaults */
  if (!port || strlen(port) == 0) port = "8554";
  if (!path || strlen(path) == 0) path = "/stream";
  if (!realm || strlen(realm) == 0) realm = "RPi Camera";
  if (!auth_method || strlen(auth_method) == 0) auth_method = "both";

  gst_init (&argc, &argv);

  if (argc < 2) {
    g_print ("Usage: %s <launch_string>\n", argv[0]);
    g_print ("\nEnvironment variables:\n");
    g_print ("  RTSP_PORT       - Port to listen on (default: 8554)\n");
    g_print ("  RTSP_PATH       - Mount path (default: /stream)\n");
    g_print ("  RTSP_USER       - Username for authentication (optional)\n");
    g_print ("  RTSP_PASSWORD   - Password for authentication (optional)\n");
    g_print ("  RTSP_REALM      - Authentication realm (default: \"RPi Camera\")\n");
    g_print ("  RTSP_AUTH_METHOD- basic, digest, or both (default: both)\n");
    return -1;
  }

  loop = g_main_loop_new (NULL, FALSE);

  server = gst_rtsp_server_new ();
  gst_rtsp_server_set_service (server, port);

  mounts = gst_rtsp_server_get_mount_points (server);

  /* Create media factory */
  str = g_strdup_printf ("( %s )", argv[1]);
  factory = gst_rtsp_media_factory_new ();
  gst_rtsp_media_factory_set_launch (factory, str);
  gst_rtsp_media_factory_set_shared (factory, TRUE);
  g_free (str);

  /* Setup authentication if username and password are provided */
  if (user && password && strlen(user) > 0 && strlen(password) > 0) {
    g_print ("[AUTH] Enabling authentication for user: %s (method: %s)\n", user, auth_method);
    
    auth = gst_rtsp_auth_new ();
    
    /* Set the realm for authentication challenges */
    gst_rtsp_auth_set_realm (auth, realm);
    
    /* Create a token with media factory access permissions */
    token = gst_rtsp_token_new (
        GST_RTSP_TOKEN_MEDIA_FACTORY_ROLE, G_TYPE_STRING, "user",
        NULL);
    
    /* Add Basic authentication if requested */
    if (g_strcmp0(auth_method, "basic") == 0 || g_strcmp0(auth_method, "both") == 0) {
      basic = gst_rtsp_auth_make_basic (user, password);
      gst_rtsp_auth_add_basic (auth, basic, token);
      g_free (basic);
      g_print ("[AUTH] Basic authentication enabled\n");
    }
    
    /* Add Digest authentication if requested */
    if (g_strcmp0(auth_method, "digest") == 0 || g_strcmp0(auth_method, "both") == 0) {
      gst_rtsp_auth_add_digest (auth, user, password, token);
      g_print ("[AUTH] Digest authentication enabled\n");
    }
    
    gst_rtsp_token_unref (token);
    
    /* Set the authentication on the server */
    gst_rtsp_server_set_auth (server, auth);
    
    /* Add role permission to access the media factory */
    gst_rtsp_media_factory_add_role (factory, "user",
        GST_RTSP_PERM_MEDIA_FACTORY_ACCESS, G_TYPE_BOOLEAN, TRUE,
        GST_RTSP_PERM_MEDIA_FACTORY_CONSTRUCT, G_TYPE_BOOLEAN, TRUE,
        NULL);
    
    g_print ("[AUTH] Authentication configured successfully\n");
  } else {
    g_print ("[AUTH] Authentication disabled (no RTSP_USER/RTSP_PASSWORD set)\n");
  }

  /* Mount the factory */
  gst_rtsp_mount_points_add_factory (mounts, path, factory);
  g_object_unref (mounts);

  /* Attach server to main context */
  if (gst_rtsp_server_attach (server, NULL) == 0) {
    g_print ("Failed to attach the server\n");
    return -1;
  }

  /* Cleanup sessions periodically */
  g_timeout_add_seconds (2, (GSourceFunc) timeout_callback, server);

  /* Print stream URL */
  if (user && password && strlen(user) > 0 && strlen(password) > 0) {
    g_print ("stream ready at rtsp://%s:%s@127.0.0.1:%s%s (authenticated, method=%s)\n", 
             user, "****", port, path, auth_method);
  } else {
    g_print ("stream ready at rtsp://127.0.0.1:%s%s (no authentication)\n", 
             port, path);
  }
  
  g_main_loop_run (loop);

  /* Cleanup */
  if (auth) {
    g_object_unref (auth);
  }

  return 0;
}
