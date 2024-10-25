Widgets
=======

The TOM uses a number of custom widgets to display information in a more user-friendly way. These widgets are
implemented as Django template tags and can be used in any template.
Be sure to include ``{% load tom_common_extras %}`` at the top of your template to load the required tags.

Copy Button:
------------
.. automodule:: tom_common.templatetags.tom_common_extras.copy_button
    :members:

Popup Notification (Toast):
---------------------------

If you wish to add a small, but obvious, non-intrusive popup notification that will temporarily appear at the top
of the page (commonly referred to as a Toast Notification), the TOMtoolkit provides the following strategy to do so.

Add the toast class to a div to create a temporary notification at the top of the TOM.
Add something like the following codeblock to your template. Anything that can trigger a javascript function can be
used to show the toast.

.. code-block:: html

    <button onclick="ShowToast()">Show Toast</button>
    <div id="toast_window" class="toast">Thing inside the toast window! </div>

    {% block scripts %}
    <script>
      function ShowToast() {
      // Get the toast DIV
      var x = document.getElementById("toast_window");

      // Add the "show" class to DIV
      x.className += " show";

      // After 3 seconds, remove the show class from DIV
      setTimeout(function(){ x.className = x.className.replace("show", ""); }, 3000);
    }
    </script>
    {% endblock scripts %}

Change the background color of the toast by adding a class to the toast div.
i.e. ``class="toast warning"`` will change the background color to yellow (unless you have changed your root colors):

|image0|

The following classes are available:
 - primary
 - info
 - success
 - warning
 - danger

.. |image0| image:: /_static/customize_templates_doc/toast_example.png
