(function () {
  'use strict';

  function initAladin(targetRa, targetDec) {
    let aladin;
    A.init.then(() => {
      aladin = A.aladin('#aladin-lite-div', {
        survey: 'P/DSS2/color',
        fov: getFovAsDegreesFromForm(),
        showReticle: false,
        target: String(targetRa) + ' ' + String(targetDec),
        showGotoControl: false,
        showZoomControl: false
      });

      aladin.on('positionChanged', function () {
        annotateChart(targetRa, targetDec);
      });

      aladin.on('zoomChanged', function () {
        annotateChart(targetRa, targetDec);
      });
    });

    function getScaleBarFromForm() {
      const scaleBarSizeInput = document.getElementById('scale-bar-size');
      const scaleBarUnitsSelect = document.getElementById('scale-bar-units-select');
      let size = Number(scaleBarSizeInput.value);
      if (size < 0) {
        size = 0;
      }
      const units = scaleBarUnitsSelect.value;
      const label = String(size) + ' ' + units;
      const sizeAsDegrees = toDegrees(size, units);
      return {size: size, units: units, label: label, sizeAsDegrees: sizeAsDegrees};
    }

    function getFovAsDegreesFromForm() {
      const fovInput = document.getElementById('fov');
      const fovUnitsSelect = document.getElementById('fov-units-select');
      const fov = Number(fovInput.value);
      const units = fovUnitsSelect.value;
      let fovAsDegrees;
      if (fov >= 0) {
        fovAsDegrees = toDegrees(fov, units);
      }
      return fovAsDegrees;
    }

    function toDegrees(value, units) {
      if (units === 'arcmin') {
        return value / 60;
      } else if (units === 'arcsec') {
        return value / 3600;
      } else {
        return value;
      }
    }

    function annotateChart(targetRaValue, targetDecValue) {
      const fovDegrees = aladin.getFov()[0];
      const scaleBar = getScaleBarFromForm();
      // Pixel position (0,0) is the top left corner of the view
      const viewSizePix = aladin.getSize();
      const offsetPixFromEdge = 30;
      const scaleBarStartPix = [offsetPixFromEdge, viewSizePix[1] - offsetPixFromEdge]; // Bottom left corner
      const compassCenterPix = [viewSizePix[0] - offsetPixFromEdge, viewSizePix[1] - offsetPixFromEdge]; // Bottom right corner
      // Compass position
      const cosDec = Math.cos(targetDecValue * Math.PI / 180);
      const compassArmLength = fovDegrees / 10;
      const compassCenter = aladin.pix2world(compassCenterPix[0], compassCenterPix[1]);
      const compassNorthArm = [compassCenter[0], compassCenter[1] + compassArmLength];
      const compassNorthArmPix = aladin.world2pix(compassNorthArm[0], compassNorthArm[1]);
      const compassEastArm = [compassCenter[0] + compassArmLength / cosDec, compassCenter[1]];
      const compassEastArmPix = aladin.world2pix(compassEastArm[0], compassEastArm[1]);
      // Scale bar position
      const scaleBarStart = aladin.pix2world(scaleBarStartPix[0], scaleBarStartPix[1]);
      const scaleBarEnd = [scaleBarStart[0] - scaleBar.sizeAsDegrees / cosDec, scaleBarStart[1]];
      const scaleBarEndPix = aladin.world2pix(scaleBarEnd[0], scaleBarEnd[1]);
      const scaleBarLength = Math.abs(scaleBarEndPix[0] - scaleBarStartPix[0]);
      // Re-draw the annotations on the chart
      const color = '#f72525';
      const scaleBarTextSpacing = 7;
      const compassTextSpacing = 3;
      aladin.removeLayers();
      let layer = A.graphicOverlay({name: 'chart annotations', color: color, lineWidth: 2});
      aladin.addOverlay(layer);
      layer.add(A.polyline([compassNorthArm, compassCenter, compassEastArm]));
      layer.add(A.polyline([scaleBarStart, scaleBarEnd]));
      layer.add(A.circle(targetRaValue, targetDecValue, fovDegrees / 30));
      layer.add(new Text(scaleBarStartPix[0] + scaleBarLength / 2, scaleBarStartPix[1] - scaleBarTextSpacing, scaleBar.label, {color: color}));
      layer.add(new Text(compassNorthArmPix[0], compassNorthArmPix[1] - compassTextSpacing, 'N', {color: color}));
      layer.add(new Text(compassEastArmPix[0] - compassTextSpacing, compassEastArmPix[1], 'E', {color: color, align: 'end', baseline: 'middle'}));
    }

    function downloadImage() {
      // Update the data that the link that was clicked will download
      document.getElementById('download-chart').setAttribute('href', aladin.getViewDataURL());
      return true;
    }

    function updateFromForm(ra, dec) {
      const fov = getFovAsDegreesFromForm();
      if (fov !== undefined) {
        aladin.setFov(fov);
        annotateChart(ra, dec);
      }
    }

    var Text = (function () {
      // The AladinLite API does not provide a way to draw arbitrary text at an arbitrary location in an overlay layer.
      // This implements the methods necessary to do so when provided as an input to layer.add(). This approach was
      // preferable to the others (possibilities included directly getting and drawing on the actual canvas element that the
      // other overlay elements are drawn on, or creating another canvas element and placing it directly on top of
      // the others) as the text that is drawn will then be integrated with the draw/destroy/redraw loops within aladin,
      // and the text will show up in the generated data url that is used for saving an image without having to do anything extra.

      Text = function (x, y, text, options) {
        options = options || {};
        this.x = x || undefined;
        this.y = y || undefined;
        this.text = text || '';
        this.color = options.color || undefined;
        this.align = options.align || 'center';
        this.baseline = options.baseline || 'alphabetic';
        this.overlay = null;
      };

      Text.prototype.setOverlay = function (overlay) {
        this.overlay = overlay;
      };

      Text.prototype.draw = function (ctx) {
        ctx.fillStyle = this.color;
        ctx.font = '15px Arial';
        ctx.textAlign = this.align;
        ctx.textBaseline = this.baseline;
        ctx.fillText(this.text, this.x, this.y);
      };

      return Text;
    })();

    document.getElementById('update-finderchart').addEventListener('click', function () {
      updateFromForm(targetRa, targetDec);
    });

    document.getElementById('download-chart').addEventListener('click', function () {
      downloadImage();
    });
  }

  function bootstrapFinderchart() {
    const finderchart = document.querySelector('.js-aladin-finderchart');
    if (!finderchart || !window.A || !window.A.init) {
      return;
    }

    const targetRa = Number(finderchart.dataset.targetRa);
    const targetDec = Number(finderchart.dataset.targetDec);
    if (!Number.isFinite(targetRa) || !Number.isFinite(targetDec)) {
      return;
    }

    initAladin(targetRa, targetDec);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapFinderchart);
  } else {
    bootstrapFinderchart();
  }
})();
