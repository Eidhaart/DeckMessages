package dev.eidhaart.deckmessages

import android.os.Bundle
import android.view.View
import androidx.activity.enableEdgeToEdge
import androidx.core.graphics.Insets
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

class MainActivity : TauriActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    enableEdgeToEdge()
    super.onCreate(savedInstanceState)

    // Edge-to-edge apps don't get resized for the keyboard automatically, so the WebView
    // would slide up under it. Shrink the content to sit above the keyboard instead, and
    // drop the bottom bar inset while it's open so the page doesn't add a gap for it.
    val content = findViewById<View>(android.R.id.content)
    ViewCompat.setOnApplyWindowInsetsListener(content) { view, insets ->
      val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
      view.setPadding(0, 0, 0, ime.bottom)
      if (ime.bottom > 0) {
        val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
        WindowInsetsCompat.Builder(insets)
          .setInsets(WindowInsetsCompat.Type.systemBars(), Insets.of(bars.left, bars.top, bars.right, 0))
          .build()
      } else {
        insets
      }
    }
  }
}
